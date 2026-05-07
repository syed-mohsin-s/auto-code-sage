from typing import TypedDict, List
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from utils.context_loader import load_engineering_standards

load_dotenv()

# --- State Definition ---
class AgentState(TypedDict):
    diff: str
    pr_details: dict
    security_review: str
    optimization_review: str
    review_comment: str

# --- LLM Setup ---
llm = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID", "qwen.qwen3-coder-30b-a3b-v1:0"),
    temperature=0.2,
    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
)

# --- Structured Output Models ---
class SecurityReviewOutput(BaseModel):
    """Structured output for the Security Auditor agent."""
    critical_vulns: List[str] = Field(
        default_factory=list,
        description="List of severe security vulnerabilities found (OWASP Top 10, injections, XSS, exposed secrets, etc.)."
    )
    notes: str = Field(
        default="",
        description="General security observations or summary."
    )

class OptimizationReviewOutput(BaseModel):
    """Structured output for the Performance Engineer agent."""
    performance_issues: List[str] = Field(
        default_factory=list,
        description="List of performance bottlenecks found (Big-O issues, DRY violations, memory leaks, anti-patterns, etc.)."
    )
    notes: str = Field(
        default="",
        description="General optimization observations or summary."
    )

# --- Analysis Nodes (Parallel Execution) ---

def analyze_security(state: AgentState):
    """
    Dedicated Security Auditor agent.
    Focuses exclusively on security vulnerabilities to avoid attention dilution.
    """
    print("[SECURITY AGENT] Analyzing code diff for vulnerabilities...")
    diff = state.get("diff", "")

    company_standards = load_engineering_standards()

    prompt = f"""You are a **Senior Security Auditor** with deep expertise in application security.

CRITICAL CONTEXT - COMPANY ENGINEERING STANDARDS:
<company_standards>
{company_standards}
</company_standards>

Your task is to review the following code diff and identify ONLY security-related issues against our specific company standards and general OWASP principles.

**Your scope is strictly limited to:**
- Adherence to the company_standards provided
- OWASP Top 10 vulnerabilities
- SQL and NoSQL injection vectors
- Cross-Site Scripting (XSS) risks
- Exposed secrets, API keys, or credentials hardcoded in source
- Authentication and authorization flaws
- Insecure deserialization
- Server-Side Request Forgery (SSRF)
- Path traversal and file inclusion vulnerabilities
- Use of known-vulnerable dependencies or cryptographic primitives
- Any other severe security vulnerability

**You MUST NOT comment on:**
- Code style, formatting, or naming conventions
- Performance or optimization concerns
- General code quality or refactoring suggestions

**Code Diff:**
```
{diff[:20000]}
```

**Output Format:**
For each issue found, provide:
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW
- **Location**: The relevant code snippet or line reference
- **Issue**: Clear description of the vulnerability
- **Recommendation**: Specific fix or mitigation

If no security issues are found, respond with:
"No security vulnerabilities detected in this diff."
"""

    messages = [
        SystemMessage(content="You are a strict security-focused code reviewer. Always adhere to the company_standards provided. You never comment on style or performance — only security."),
        HumanMessage(content=prompt)
    ]

    structured_llm = llm.with_structured_output(SecurityReviewOutput)
    result: SecurityReviewOutput = structured_llm.invoke(messages)

    # Format the structured output into a readable Markdown string
    vuln_lines = "\n".join(f"- {v}" for v in result.critical_vulns) if result.critical_vulns else "_No critical vulnerabilities detected._"
    formatted = f"**Critical Vulnerabilities:**\n{vuln_lines}\n\n**Notes:** {result.notes}"

    return {"security_review": formatted}


def analyze_optimization(state: AgentState):
    """
    Dedicated Performance Engineer agent.
    Focuses exclusively on performance and code quality to avoid attention dilution.
    """
    print("[OPTIMIZATION AGENT] Analyzing code diff for performance issues...")
    diff = state.get("diff", "")

    company_standards = load_engineering_standards()

    prompt = f"""You are a **Senior Performance Engineer** with deep expertise in software optimization.

CRITICAL CONTEXT - COMPANY ENGINEERING STANDARDS:
<company_standards>
{company_standards}
</company_standards>

Your task is to review the following code diff and identify ONLY performance and code quality issues against our specific company standards.

**Your scope is strictly limited to:**
- Adherence to the company_standards provided
- Algorithmic complexity concerns (Big-O analysis of loops, data structures, searches)
- DRY (Don't Repeat Yourself) principle violations and code duplication
- Memory leaks, unnecessary allocations, or resource management issues
- Language-specific anti-patterns and idiomatic improvements
- Inefficient database queries (N+1 problems, missing indexes, unbounded SELECTs)
- Caching opportunities and redundant computations
- Concurrency issues (race conditions, deadlocks, thread-safety)
- Unnecessary I/O operations or blocking calls

**You MUST NOT comment on:**
- Security vulnerabilities or authentication concerns
- Code formatting or stylistic preferences unrelated to performance
- General feature suggestions

**Code Diff:**
```
{diff[:20000]}
```

**Output Format:**
For each issue found, provide:
- **Impact**: HIGH / MEDIUM / LOW
- **Location**: The relevant code snippet or line reference
- **Issue**: Clear description of the performance concern
- **Recommendation**: Specific optimization with rationale

If no optimization issues are found, respond with:
"No performance or optimization issues detected in this diff."
"""

    messages = [
        SystemMessage(content="You are a strict performance-focused code reviewer. Always adhere to the company_standards provided. You never comment on security or style — only performance and optimization."),
        HumanMessage(content=prompt)
    ]

    structured_llm = llm.with_structured_output(OptimizationReviewOutput)
    result: OptimizationReviewOutput = structured_llm.invoke(messages)

    # Format the structured output into a readable Markdown string
    issue_lines = "\n".join(f"- {i}" for i in result.performance_issues) if result.performance_issues else "_No performance issues detected._"
    formatted = f"**Performance Issues:**\n{issue_lines}\n\n**Notes:** {result.notes}"

    return {"optimization_review": formatted}


# --- Synthesis Node ---

def format_final_review(state: AgentState):
    """
    Synthesizer node that combines the security and optimization reviews
    into a single, polished Markdown report for the PR comment.
    """
    print("[SYNTHESIZER] Combining specialist reviews into final report...")

    security_review = state.get("security_review", "No security review available.")
    optimization_review = state.get("optimization_review", "No optimization review available.")
    pr_details = state.get("pr_details", {})

    pr_title = pr_details.get("title", "Untitled PR")

    final_comment = f"""## 🤖 Auto Code Sage — AI Review Report

**PR:** {pr_title}

---

### 🔒 Security Analysis

{security_review}

---

### ⚡ Performance & Optimization Analysis

{optimization_review}

---

> _This review was generated by **Auto Code Sage** using parallel multi-agent analysis.
> Each section above was produced by a dedicated specialist agent to ensure focused, high-quality feedback._
"""

    return {"review_comment": final_comment}


# --- Graph Construction ---
workflow = StateGraph(AgentState)

# Add the three specialist nodes
workflow.add_node("security_agent", analyze_security)
workflow.add_node("optimization_agent", analyze_optimization)
workflow.add_node("synthesizer", format_final_review)

# Parallel fan-out: both analysis agents start simultaneously from START
workflow.add_edge(START, "security_agent")
workflow.add_edge(START, "optimization_agent")

# Fan-in: both analysis agents feed into the synthesizer
workflow.add_edge("security_agent", "synthesizer")
workflow.add_edge("optimization_agent", "synthesizer")

# Synthesizer produces the final output
workflow.add_edge("synthesizer", END)

# Compile the graph
app = workflow.compile()

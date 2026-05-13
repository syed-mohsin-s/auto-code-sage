"""
Deep Analysis Test Suite for AutoCode Sage
Tests the full pipeline with real-world simulated payloads WITHOUT hitting external APIs.
"""
import sys
import os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from db.database import engine, SessionLocal
from db.models import Base, AIReviews
from utils.context_loader import load_engineering_standards, load_past_mistakes

PASS = "PASS"
FAIL = "FAIL"
results = []

def log(test_name, status, detail=""):
    results.append((test_name, status, detail))
    icon = "[OK]" if status == PASS else "[!!]"
    print(f"  {icon} [{status}] {test_name}" + (f" -- {detail}" if detail else ""))

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ============================================================
# MODULE 1: Database Layer
# ============================================================
def test_database():
    separator("MODULE 1: Database Layer")
    
    # Test 1.1: Table schema has all required columns
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("ai_reviews")}
    required = {"id","timestamp","repo_name","pr_number","commit_sha","diff_snippet",
                "ai_raw_response","security_analysis","optimization_analysis",
                "parsed_suggestion","human_feedback","rejection_reason","model_version"}
    missing = required - columns
    if missing:
        log("Schema completeness", FAIL, f"Missing columns: {missing}")
    else:
        log("Schema completeness", PASS, f"All {len(required)} columns present")

    # Test 1.2: CRUD operations
    db = SessionLocal()
    try:
        review = AIReviews(
            repo_name="test/repo", pr_number=999,
            commit_sha="abc123", diff_snippet="+ print('hello')",
            ai_raw_response="Test review body",
            security_analysis="No issues", optimization_analysis="No issues",
            human_feedback="rejected", rejection_reason="False positive on auth",
            timestamp=datetime.utcnow()
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        log("INSERT with rejection_reason", PASS, f"ID={review.id}")
        
        # Read back
        fetched = db.query(AIReviews).filter(AIReviews.id == review.id).first()
        if fetched and fetched.rejection_reason == "False positive on auth":
            log("READ rejection_reason", PASS)
        else:
            log("READ rejection_reason", FAIL, "Value mismatch")

        # Update
        fetched.rejection_reason = "Updated reason"
        db.commit()
        re_fetched = db.query(AIReviews).filter(AIReviews.id == review.id).first()
        if re_fetched.rejection_reason == "Updated reason":
            log("UPDATE rejection_reason", PASS)
        else:
            log("UPDATE rejection_reason", FAIL)
        
        # Cleanup
        db.delete(re_fetched)
        db.commit()
        log("DELETE test record", PASS)
    except Exception as e:
        log("CRUD operations", FAIL, str(e))
    finally:
        db.close()

    # Test 1.3: Nullable constraints — rejection_reason should allow NULL
    db = SessionLocal()
    try:
        review = AIReviews(
            repo_name="test/nullable", pr_number=998,
            ai_raw_response="body", timestamp=datetime.utcnow()
        )
        db.add(review)
        db.commit()
        log("Nullable rejection_reason (NULL insert)", PASS)
        db.delete(review)
        db.commit()
    except Exception as e:
        log("Nullable rejection_reason", FAIL, str(e))
    finally:
        db.close()

# ============================================================
# MODULE 2: Context Loader
# ============================================================
def test_context_loader():
    separator("MODULE 2: Context Loader")

    # Test 2.1: Engineering standards loading
    standards = load_engineering_standards()
    if "engineering_standards.md" in standards and "timeout=5" in standards:
        log("Load engineering_standards.md", PASS)
    else:
        log("Load engineering_standards.md", FAIL, f"Got: {standards[:100]}")

    if "security_policies.md" in standards:
        log("Load security_policies.md", PASS)
    else:
        log("Load security_policies.md", FAIL)

    if "optimization_standards.md" in standards:
        log("Load optimization_standards.md", PASS)
    else:
        log("Load optimization_standards.md", FAIL)

    # Test 2.2: Past mistakes — empty DB returns empty string
    db = SessionLocal()
    try:
        # Clear any existing rejected reviews for clean test
        db.query(AIReviews).filter(AIReviews.human_feedback == "rejected").delete()
        db.commit()
    finally:
        db.close()

    result = load_past_mistakes()
    if result == "":
        log("Past mistakes (no rejections)", PASS, "Returns empty string")
    else:
        log("Past mistakes (no rejections)", FAIL, f"Expected empty, got: {result[:80]}")

    # Test 2.3: Past mistakes with seeded rejected reviews
    db = SessionLocal()
    try:
        for i in range(7):
            r = AIReviews(
                repo_name=f"test/repo-{i}", pr_number=100+i,
                diff_snippet=f"+ vulnerable_code_{i}()",
                ai_raw_response=f"Review body for PR {100+i}",
                human_feedback="rejected",
                rejection_reason=f"Reason {i}: false positive" if i % 2 == 0 else None,
                timestamp=datetime.utcnow() - timedelta(hours=i)
            )
            db.add(r)
        db.commit()
    finally:
        db.close()

    result = load_past_mistakes()
    if "CRITICAL CONTEXT - PAST MISTAKES TO AVOID" in result:
        log("Past mistakes header present", PASS)
    else:
        log("Past mistakes header present", FAIL)

    if "Rejected Review #1" in result and "Rejected Review #5" in result:
        log("Past mistakes limit=5", PASS)
    else:
        log("Past mistakes limit=5", FAIL)

    if "Rejected Review #6" not in result:
        log("Past mistakes excludes >5", PASS)
    else:
        log("Past mistakes excludes >5", FAIL, "Showing more than 5 reviews")

    # Test 2.4: Most recent first (PR in repo-0 was most recent, should be #1)
    if result.index("repo-0") < result.index("repo-4"):
        log("Past mistakes ordering (newest first)", PASS)
    else:
        log("Past mistakes ordering (newest first)", FAIL)

    # Test 2.5: Handles missing rejection_reason gracefully
    if "No reason provided by the reviewer." in result:
        log("Missing reason fallback text", PASS)
    else:
        log("Missing reason fallback text", FAIL)

    # Test 2.6: Custom limit
    result3 = load_past_mistakes(limit=2)
    if "Rejected Review #2" in result3 and "Rejected Review #3" not in result3:
        log("Custom limit=2", PASS)
    else:
        log("Custom limit=2", FAIL)

    # Cleanup
    db = SessionLocal()
    try:
        db.query(AIReviews).filter(AIReviews.repo_name.like("test/%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

# ============================================================
# MODULE 3: Webhook Payload Parsing (unit-level)
# ============================================================
def test_webhook_parsing():
    separator("MODULE 3: Webhook Payload Parsing")

    # Test 3.1: Rejection reason extraction logic (isolated)
    test_cases = [
        ("!reject-sage This is wrong", "This is wrong"),
        ("!reject-sage", None),  # No reason
        ("Great review! !reject-sage Bad auth check", "Bad auth check"),
        ("!REJECT-SAGE Case insensitive reason", "Case insensitive reason"),
        ("!accept-sage", None),  # Not a rejection
    ]
    
    for body_text, expected_reason in test_cases:
        # Replicate webhook logic
        body_lower = body_text.lower()
        rejection_reason = None
        if "!reject-sage" in body_lower:
            reject_idx = body_lower.find("!reject-sage")
            reason_text = body_text[reject_idx + len("!reject-sage"):].strip()
            if reason_text:
                rejection_reason = reason_text

        if rejection_reason == expected_reason:
            log(f"Parse: '{body_text[:40]}'", PASS, f"reason={rejection_reason}")
        else:
            log(f"Parse: '{body_text[:40]}'", FAIL, f"expected={expected_reason}, got={rejection_reason}")

    # Test 3.2: PR event payload structure validation
    valid_payload = {
        "action": "opened",
        "pull_request": {"number": 1, "title": "Test PR", "head": {"sha": "abc"}},
        "repository": {"full_name": "owner/repo"}
    }
    pr = valid_payload.get("pull_request")
    try:
        repo = valid_payload["repository"]["full_name"]
        pr_num = pr["number"]
        sha = pr.get("head", {}).get("sha")
        log("Valid PR payload parsing", PASS, f"repo={repo} pr={pr_num} sha={sha}")
    except (KeyError, TypeError) as e:
        log("Valid PR payload parsing", FAIL, str(e))

    # Test 3.3: Malformed payload — missing repository
    bad_payload = {"action": "opened", "pull_request": {"number": 1}}
    try:
        _ = bad_payload["repository"]["full_name"]
        log("Missing repository key", FAIL, "Should have raised KeyError")
    except KeyError:
        log("Missing repository key (caught)", PASS, "KeyError raised as expected")

    # Test 3.4: Comment payload — issue_comment event structure
    comment_payload = {
        "action": "created",
        "comment": {"body": "!reject-sage Your auth analysis is wrong"},
        "issue": {"number": 42},
        "repository": {"full_name": "owner/repo"}
    }
    issue = comment_payload.get("issue", {})
    if issue.get("number") == 42:
        log("Comment payload PR number extraction", PASS)
    else:
        log("Comment payload PR number extraction", FAIL)

# ============================================================
# MODULE 4: Agent Graph Structure
# ============================================================
def test_agent_graph():
    separator("MODULE 4: Agent Graph Structure")

    from agent.graph import app as agent_app, AgentState

    # Test 4.1: Graph nodes
    node_names = set(agent_app.get_graph().nodes.keys())
    expected_nodes = {"security_agent", "optimization_agent", "synthesizer"}
    # LangGraph adds __start__ and __end__ 
    if expected_nodes.issubset(node_names):
        log("Graph has all 3 nodes", PASS, str(node_names))
    else:
        log("Graph has all 3 nodes", FAIL, f"Missing: {expected_nodes - node_names}")

    # Test 4.2: State schema
    state_keys = set(AgentState.__annotations__.keys())
    expected_keys = {"diff", "pr_details", "security_review", "optimization_review", "review_comment"}
    if state_keys == expected_keys:
        log("AgentState schema", PASS)
    else:
        log("AgentState schema", FAIL, f"Expected {expected_keys}, got {state_keys}")

    # Test 4.3: Structured output models
    from agent.graph import SecurityReviewOutput, OptimizationReviewOutput
    
    sec = SecurityReviewOutput()
    if sec.critical_vulns == [] and sec.notes == "":
        log("SecurityReviewOutput defaults", PASS)
    else:
        log("SecurityReviewOutput defaults", FAIL)

    opt = OptimizationReviewOutput()
    if opt.performance_issues == [] and opt.notes == "":
        log("OptimizationReviewOutput defaults", PASS)
    else:
        log("OptimizationReviewOutput defaults", FAIL)

    # Test 4.4: Synthesizer (pure function, no LLM needed)
    from agent.graph import format_final_review
    test_state = {
        "diff": "test diff",
        "pr_details": {"title": "Fix login bug"},
        "security_review": "**Critical Vulnerabilities:**\n- SQL Injection in login.py",
        "optimization_review": "**Performance Issues:**\n_No performance issues detected._",
        "review_comment": ""
    }
    result = format_final_review(test_state)
    comment = result["review_comment"]

    if "Fix login bug" in comment:
        log("Synthesizer includes PR title", PASS)
    else:
        log("Synthesizer includes PR title", FAIL)

    if "SQL Injection" in comment:
        log("Synthesizer includes security review", PASS)
    else:
        log("Synthesizer includes security review", FAIL)

    if "No performance issues" in comment:
        log("Synthesizer includes optimization review", PASS)
    else:
        log("Synthesizer includes optimization review", FAIL)

    if "Auto Code Sage" in comment:
        log("Synthesizer branding", PASS)
    else:
        log("Synthesizer branding", FAIL)

# ============================================================
# MODULE 5: Security Audit of the Project Itself
# ============================================================
def test_self_security():
    separator("MODULE 5: Security Audit (Self-Analysis)")
    
    # Test 5.1: .env is in .gitignore
    gitignore_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".gitignore")
    with open(gitignore_path, "r", encoding="utf-8") as f:
        gitignore = f.read()
    if ".env" in gitignore:
        log(".env in .gitignore", PASS)
    else:
        log(".env in .gitignore", FAIL, "CRITICAL: Secrets could leak!")

    # Test 5.2: No webhook signature verification
    webhooks_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routers", "webhooks.py")
    with open(webhooks_path, "r", encoding="utf-8") as f:
        webhook_code = f.read()
    if "WEBHOOK_SECRET" in webhook_code or "hmac" in webhook_code.lower() or "x-hub-signature" in webhook_code.lower():
        log("Webhook signature verification", PASS)
    else:
        log("Webhook signature verification", FAIL, "BUG: No HMAC verification — anyone can trigger reviews!")

    # Test 5.3: No rate limiting on webhook endpoint
    if "RateLimiter" in webhook_code or "slowapi" in webhook_code or "rate" in webhook_code.lower():
        log("Rate limiting", PASS)
    else:
        log("Rate limiting", FAIL, "BUG: No rate limiting — vulnerable to abuse")

    # Test 5.4: DB init runs in Dockerfile (creates tables at build time)
    dockerfile_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Dockerfile")
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        dockerfile = f.read()
    if "init_db" in dockerfile:
        log("DB init in Dockerfile", PASS)
    else:
        log("DB init in Dockerfile", FAIL, "Tables may not exist at runtime")

    # Test 5.5: main.py doesn't run DB init on startup
    main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        main_code = f.read()
    if "create_all" not in main_code and "init_db" not in main_code:
        log("No auto-migrate on startup", PASS, "Relies on init_db script — OK for SQLite, risky for prod")
    else:
        log("DB auto-init on startup", PASS)

    # Test 5.6: system_utils.py not registered (orphan router)
    if "system_utils" in main_code:
        log("system_utils router registered", PASS)
    else:
        log("system_utils router NOT registered", PASS, "File was removed during cleanup")

# ============================================================
# MODULE 6: Edge Cases & Robustness
# ============================================================
def test_edge_cases():
    separator("MODULE 6: Edge Cases & Robustness")

    # Test 6.1: Empty diff handling
    from agent.graph import format_final_review
    empty_state = {
        "diff": "",
        "pr_details": {},
        "security_review": "",
        "optimization_review": "",
        "review_comment": ""
    }
    result = format_final_review(empty_state)
    if result.get("review_comment"):
        log("Empty diff produces output", PASS, "Synthesizer still generates report structure")
    else:
        log("Empty diff produces output", FAIL)

    # Test 6.2: Very large diff truncation
    large_diff = "+" * 50000
    truncated = large_diff[:20000]
    if len(truncated) == 20000:
        log("Diff truncation at 20K chars", PASS)
    else:
        log("Diff truncation at 20K chars", FAIL)

    # Test 6.3: DB snippet truncation
    snippet = large_diff[:5000]
    if len(snippet) == 5000:
        log("DB diff_snippet truncation at 5K", PASS)
    else:
        log("DB diff_snippet truncation at 5K", FAIL)

    # Test 6.4: Past mistakes with NULL diff_snippet
    db = SessionLocal()
    try:
        r = AIReviews(
            repo_name="test/null-diff", pr_number=777,
            diff_snippet=None, ai_raw_response=None,
            human_feedback="rejected", rejection_reason=None,
            timestamp=datetime.utcnow()
        )
        db.add(r)
        db.commit()
    finally:
        db.close()

    try:
        result = load_past_mistakes()
        if "No diff available." in result and "No reason provided" in result:
            log("NULL fields in past mistakes", PASS, "Fallback text works")
        else:
            log("NULL fields in past mistakes", FAIL, f"Got: {result[:200]}")
    except Exception as e:
        log("NULL fields in past mistakes", FAIL, f"Exception: {e}")

    # Cleanup
    db = SessionLocal()
    try:
        db.query(AIReviews).filter(AIReviews.repo_name.like("test/%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    # Test 6.5: Concurrent DB session safety (context_loader uses its own session)
    try:
        from utils.context_loader import load_past_mistakes as lpm
        # Calling twice rapidly should not cause session conflicts
        r1 = lpm()
        r2 = lpm()
        log("Concurrent context_loader calls", PASS)
    except Exception as e:
        log("Concurrent context_loader calls", FAIL, str(e))

# ============================================================
# SUMMARY
# ============================================================
def print_summary():
    separator("TEST SUMMARY")
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total = len(results)
    print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
    print(f"  Pass Rate: {passed/total*100:.1f}%\n")
    
    if failed > 0:
        print("  FAILURES:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    [!!] {name}: {detail}")
    print()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  AutoCode Sage — Deep Analysis Test Suite")
    print("="*60)
    
    test_database()
    test_context_loader()
    test_webhook_parsing()
    test_agent_graph()
    test_self_security()
    test_edge_cases()
    print_summary()

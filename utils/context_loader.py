import os
from sqlalchemy import desc

def load_engineering_standards() -> str:
    # Use absolute path based on the project root to avoid working directory issues
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rules_dir = os.path.join(base_dir, "rules")
    
    combined_rules = []
    
    if not os.path.exists(rules_dir):
         return "No internal standards provided."
         
    for filename in os.listdir(rules_dir):
        if filename.endswith(".md"):
            with open(os.path.join(rules_dir, filename), "r", encoding="utf-8") as f:
                combined_rules.append(f"--- {filename} ---\n{f.read()}")
                
    return "\n\n".join(combined_rules)


def load_past_mistakes(limit: int = 5) -> str:
    """
    Fetches the last N rejected reviews from the database and formats them
    into a structured prompt section so the agent can learn from past mistakes.

    Returns an empty string if no rejected reviews exist, keeping the prompt clean.
    """
    from db.database import SessionLocal
    from db.models import AIReviews

    db = SessionLocal()
    try:
        rejected_reviews = (
            db.query(AIReviews)
            .filter(AIReviews.human_feedback == "rejected")
            .order_by(desc(AIReviews.timestamp))
            .limit(limit)
            .all()
        )

        if not rejected_reviews:
            return ""

        mistakes_entries = []
        for i, review in enumerate(rejected_reviews, 1):
            # Build a concise summary of each rejected review
            diff_preview = (review.diff_snippet or "No diff available.")[:2000]
            reason = review.rejection_reason or "No reason provided by the reviewer."
            repo = review.repo_name or "Unknown repo"
            pr = review.pr_number or "?"

            entry = f"""--- Rejected Review #{i} (PR #{pr} in {repo}) ---
**Diff that was reviewed:**
```
{diff_preview}
```

**AI review that was rejected:**
{(review.ai_raw_response or "N/A")[:1500]}

**Reason for rejection:**
{reason}
"""
            mistakes_entries.append(entry)

        formatted = "\n\n".join(mistakes_entries)

        return f"""CRITICAL CONTEXT - PAST MISTAKES TO AVOID:
The engineering team rejected your previous reviews for the following reasons. Do not repeat these patterns:

{formatted}

Study the above rejections carefully. Calibrate your analysis to match the engineering team's expectations. Avoid flagging issues that were previously deemed incorrect or unhelpful."""

    except Exception as e:
        print(f"[CONTEXT LOADER] Warning: Could not load past mistakes: {e}")
        return ""
    finally:
        db.close()

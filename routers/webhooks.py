from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from agent.graph import app as agent_app
from utils.github_client import get_pr_diff, post_pr_comment
from db.database import get_db
from db.models import AIReviews
from datetime import datetime, UTC
import hmac
import hashlib
import os

router = APIRouter()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

async def verify_github_signature(request: Request):
    """
    Verifies the X-Hub-Signature-256 header from GitHub webhooks
    to ensure the request is authentic and not forged.
    """
    if not WEBHOOK_SECRET:
        # If no secret is configured, skip verification (dev mode)
        return
    
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")
    
    body = await request.body()
    expected_signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

async def process_pr_event(payload: dict):
    """
    Background task to process the PR event. 
    Note: Safely getting a DB session in background task requires care, 
    often better to use a context manager or passing params differently.
    For simplicity here, we create a new session.
    """
    from db.database import SessionLocal
    db = SessionLocal()
    
    try:
        pr = payload.get("pull_request")
        if not pr:
            return

        repo_full_name = payload["repository"]["full_name"]
        pr_number = pr["number"]

        print(f"🔄 Processing PR #{pr_number} in {repo_full_name}")

        # 1. Fetch Diff
        try:
            diff_text = get_pr_diff(repo_full_name, pr_number)
        except Exception as e:
            print(f"⚠️ Failed to fetch diff: {e}")
            diff_text = ""

        # 2. Invoke Agent
        initial_state = {
            "diff": diff_text,
            "pr_details": pr,
            "security_review": "",
            "optimization_review": "",
            "review_comment": ""
        }
        
        result = agent_app.invoke(initial_state)
        review_body = result.get("review_comment", "No review generated.")

        # 3. Log to DB
        new_review = AIReviews(
            repo_name=repo_full_name,
            pr_number=pr_number,
            commit_sha=pr.get("head", {}).get("sha"),
            diff_snippet=diff_text[:5000],  # Truncate for DB
            ai_raw_response=review_body,
            security_analysis=str(result.get("security_review", "")),
            optimization_analysis=str(result.get("optimization_review", "")),
            timestamp=datetime.now(UTC)
        )
        db.add(new_review)
        db.commit()
        db.refresh(new_review)
        print(f"💾 Saved review ID {new_review.id} to DB")

        # 4. Post Comment
        # Only post if we have something substantive or if configured to always reply
        if review_body:
            post_pr_comment(repo_full_name, pr_number, review_body)

    except Exception as e:
        print(f"❌ Error processing PR: {e}")
    finally:
        db.close()

async def process_comment_event(payload: dict):
    """
    Background task to process comment feedback.
    """
    from db.database import SessionLocal
    db = SessionLocal()
    
    try:
        comment = payload.get("comment", {})
        body = comment.get("body", "").lower()
        
        feedback = None
        rejection_reason = None
        if "!accept-sage" in body:
            feedback = "accepted"
        elif "!reject-sage" in body:
            feedback = "rejected"
            # Extract the reason text after the !reject-sage command
            # e.g. "!reject-sage This was a false positive on auth check"
            original_body = comment.get("body", "")
            reject_idx = original_body.lower().find("!reject-sage")
            if reject_idx != -1:
                reason_text = original_body[reject_idx + len("!reject-sage"):].strip()
                if reason_text:
                    rejection_reason = reason_text
            
        if feedback:
            issue = payload.get("issue", {})
            pr_number = issue.get("number")
            repo_full_name = payload["repository"]["full_name"]
            
            print(f"🗣️ Received feedback '{feedback}' for PR #{pr_number}")
            
            # Update the latest review for this PR
            # In a real app, you might match by specific review ID or Comment ID context
            review = db.query(AIReviews).filter(
                AIReviews.repo_name == repo_full_name,
                AIReviews.pr_number == pr_number
            ).order_by(AIReviews.timestamp.desc()).first()
            
            if review:
                review.human_feedback = feedback
                if rejection_reason:
                    review.rejection_reason = rejection_reason
                db.commit()
                print(f"✅ Updated review ID {review.id} with feedback.{' Reason: ' + rejection_reason if rejection_reason else ''}")
            else:
                print("⚠️ No matching review found to update.")

    except Exception as e:
        print(f"❌ Error processing comment: {e}")
    finally:
        db.close()

@router.post("/github-trigger")
async def handle_github_webhook(request: Request, background_tasks: BackgroundTasks):
    await verify_github_signature(request)
    payload = await request.json()
    action = payload.get("action")
    
    # PR Opened
    if action in ["opened", "reopened", "synchronize"]:
        background_tasks.add_task(process_pr_event, payload)
        return {"status": "processing", "message": "PR review queued."}
    
    # PR Comment
    if "comment" in payload and action == "created":
        background_tasks.add_task(process_comment_event, payload)
        return {"status": "processing", "message": "Comment feedback queued."}
        
    return {"status": "ignored", "message": f"Action '{action}' not handled."}

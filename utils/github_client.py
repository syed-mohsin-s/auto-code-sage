import os
import requests
from github import Github
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
g = Github(GITHUB_TOKEN)

def get_pr_diff(repo_name: str, pr_number: int) -> str:
    """
    Fetches the diff of a Pull Request.
    """
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    # We can get the diff via the files or the raw diff url
    # Using requests to get the raw diff usually works well
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff"
    }
    response = requests.get(pr.diff_url, headers=headers)
    response.raise_for_status()
    return response.text

def post_pr_comment(repo_name: str, pr_number: int, body: str):
    """
    Posts a comment on a Pull Request.
    """
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)
    print(f"✅ Comment posted to PR #{pr_number}")

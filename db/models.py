from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class AIReviews(Base):
    __tablename__ = "ai_reviews"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    repo_name = Column(String)
    pr_number = Column(Integer)
    commit_sha = Column(String, nullable=True)
    diff_snippet = Column(Text, nullable=True)
    ai_raw_response = Column(Text)
    security_analysis = Column(Text, nullable=True)
    optimization_analysis = Column(Text, nullable=True)
    parsed_suggestion = Column(Text, nullable=True)
    human_feedback = Column(String, nullable=True) # accepted/rejected
    model_version = Column(String, default="gemini-pro")

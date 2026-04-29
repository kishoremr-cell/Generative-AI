from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    llm_source = Column(String, nullable=False, default="local")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tickets = relationship("Ticket", back_populates="job", cascade="all, delete-orphan")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    issue_key = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    acceptance_criteria = Column(Text, nullable=False)
    priority = Column(String, nullable=False)
    labels = Column(Text, nullable=False)
    comments = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("Job", back_populates="tickets")
    test_cases = relationship("TestCase", back_populates="ticket", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(String, primary_key=True, index=True)
    ticket_id = Column(String, ForeignKey("tickets.id"), nullable=False)
    source_issue_key = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    preconditions = Column(Text, nullable=False)
    steps = Column(Text, nullable=False)
    expected_result = Column(Text, nullable=False)
    priority = Column(String, nullable=False)
    test_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="test_cases")

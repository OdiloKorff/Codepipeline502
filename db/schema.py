from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime, Table, MetaData
)
from sqlalchemy.orm import registry, relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base(metadata=MetaData())

class Prompt(Base):
    __tablename__ = 'prompts'
    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    responses = relationship("Response", back_populates="prompt", cascade="all, delete")

class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey('prompts.id', ondelete='CASCADE'), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    prompt = relationship("Prompt", back_populates="responses")
    scores = relationship("Score", back_populates="response", cascade="all, delete")

class Score(Base):
    __tablename__ = 'scores'
    id = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey('responses.id', ondelete='CASCADE'), nullable=False)
    value = Column(Float, nullable=False)
    response = relationship("Response", back_populates="scores")

class Usage(Base):
    __tablename__ = 'usage'
    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey('prompts.id', ondelete='CASCADE'), nullable=False)
    tokens_used = Column(Integer, nullable=False)
    cost = Column(Float, nullable=False)
    prompt = relationship("Prompt")
import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_URL = os.getenv('TRAINING_DB_URL', 'sqlite:///training_data.db')

engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class TrainingRecord(Base):
    __tablename__ = 'training_records'
    id = Column(Integer, primary_key=True)
    prompt = Column(String, nullable=False)
    result = Column(String, nullable=False)
    ci_outcome = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)

def log_record(prompt, result, ci_outcome):
    session = Session()
    record = TrainingRecord(prompt=prompt, result=result, ci_outcome=ci_outcome)
    session.add(record)
    session.commit()
    session.close()

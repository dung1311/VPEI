from datetime import datetime
from sqlalchemy import create_engine, extract
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy import Column, Integer, DateTime
import os

engine = create_engine("sqlite:///vpei.db")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class TestModel(Base):
    __tablename__ = 'test_table'
    id = Column(Integer, primary_key=True)
    dt = Column(DateTime)

# Create table
Base.metadata.create_all(engine)

# Insert dummy data
db: Session = SessionLocal()
db.add(TestModel(dt=datetime(2023, 5, 2)))
db.commit()

# Test extract
try:
    res = db.query(TestModel).filter(extract('year', TestModel.dt) == 2023).all()
    print("Success, found rows:", len(res))
    res2 = db.query(TestModel).filter(extract('month', TestModel.dt) == 5).all()
    print("Success month, found rows:", len(res2))
except Exception as e:
    print("Error:", e)

# Clean up
db.execute(sqlalchemy.text('DROP TABLE test_table'))
db.commit()

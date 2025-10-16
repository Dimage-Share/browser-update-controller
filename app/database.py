from sqlalchemy import Column, Integer, String, DateTime, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker
import os

DB_PATH = os.getenv("DB_PATH", "/data/controller.db")
engine = create_engine(f"sqlite:///{DB_PATH}",
                       connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    browser = Column(String, index=True)
    hostname = Column(String, index=True)
    os = Column(String, index=True)
    ring = Column(String, index=True)
    version = Column(String, index=True)
    status = Column(String, index=True)
    details = Column(String)
    created_at = Column(DateTime, server_default=func.now())


def init_db():
    Base.metadata.create_all(engine)

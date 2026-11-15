from sqlalchemy import Column, Integer, String, false, true
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=true)
    email = Column(String, unique=true, nullable=false)
    hashed_password = Column(String, nullable=false)
    first_name = Column(String, nullable=false)
    last_name = Column(String, nullable=true)
    created_at = Column(String, nullable=false)
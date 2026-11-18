from fastapi import FastAPI
from sqlalchemy.orm import Session
from .core.auth.endpoints import user
from .db.database import SessionLocal, engine, Base
app = FastAPI()

Base.metadata.create_all(bind=engine)
app.include_router(user.router)

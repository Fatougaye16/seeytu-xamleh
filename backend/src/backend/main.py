from fastapi import FastAPI
from sqlalchemy.orm import Session
from .core.auth.endpoints import user
from .websearch import api
from .db.database import SessionLocal, engine, Base
app = FastAPI()

Base.metadata.create_all(bind=engine)
app.include_router(user.router)
app.include_router(api.router, prefix="/api/websearch", tags=["websearch"])

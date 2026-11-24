import chromadb
from fastapi import FastAPI
from sqlalchemy.orm import Session
from .core.auth.endpoints import user
from .websearch import api
from .db.database import SessionLocal, engine, Base
app = FastAPI()

Base.metadata.create_all(bind=engine)

from .rag.store import chroma_client, collection  # noqa: E402,F401  (shared instance)
app.include_router(user.router)
app.include_router(api.router, prefix="/api/websearch", tags=["websearch"])

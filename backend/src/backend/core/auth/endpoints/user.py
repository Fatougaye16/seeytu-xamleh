from fastapi import FastAPI
from fastapi import Depends, APIRouter
from....db.database import SessionLocal, engine, Base
from..models.user import User as UserModel
from ..schemas.user import UserCreate, User
from ....db.database import get_db
from sqlalchemy.orm import Session
router = APIRouter()

@router.post("/users/register", response_model=User, status_code=201)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = UserModel(
        id= user.id,
        username=user.username,
        email=user.email,
        hashed_password=user.hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        created_at=user.created_at
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

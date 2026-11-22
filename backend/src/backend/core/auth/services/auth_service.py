from datetime import UTC,datetime, timedelta
import datetime

from backend.core.auth.models.user import User
from pwdlib import PasswordHash
import jwt

SECRET_KEY = "set_your_secret_key_here"  # Replace with your actual secret key
ALGORITHM = "HS256"

def hashed_password(password: str):
    password_hash = PasswordHash.recommended()
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    password_hash = PasswordHash.recommended()
    return password_hash.verify(plain_password, hashed_password)

def authenticate_user(db, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(UTC) + expires_delta
    else:
        expire = datetime.datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(db, token: str):
    credentials_exception = Exception("Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user
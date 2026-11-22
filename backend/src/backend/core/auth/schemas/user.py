from pydantic import BaseModel

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    hashed_password: str
    created_at: str

class User(BaseModel):
    id: int
    first_name: str
    last_name: str
    username: str
    email: str
    created_at: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

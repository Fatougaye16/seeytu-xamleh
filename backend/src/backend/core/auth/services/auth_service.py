from pwdlib import PasswordHash

def hashed_password(password: str):
    password_hash = PasswordHash.recommended()
    return password_hash.hash(password)
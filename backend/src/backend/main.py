

from fastapi import FastAPI

app = FastAPI()

app.get("/")(lambda: {"message": "Hello World"})
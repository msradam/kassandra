import time

import jwt
from fastapi import APIRouter, HTTPException

from ..models import AuthRequest, AuthResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET = "pageturn-demo-secret"
USERS = {"admin": "pageturn123", "reader": "books456"}


def create_token(username: str) -> str:
    return jwt.encode(
        {"sub": username, "exp": int(time.time()) + 3600},
        SECRET,
        algorithm="HS256",
    )


def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/login", response_model=AuthResponse)
def login(req: AuthRequest):
    if req.username not in USERS or USERS[req.username] != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return AuthResponse(token=create_token(req.username))

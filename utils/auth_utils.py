import os
from datetime import datetime, timedelta

import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ----------------

SECRET_KEY                  = os.getenv("SECRET_KEY")
ALGORITHM                   = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

# OAuth2 scheme — tells FastAPI where to look for the token
# Frontend must send:  Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")

# ---------------- PASSWORD HASHING ----------------

def hash_password(password: str) -> str:
    """
    Hash a plain password using bcrypt.
    bcrypt is slow by design — makes brute-force attacks impractical.
    The salt is embedded in the hash, so no need to store it separately.
    """
    pwd_bytes       = password.encode("utf-8")
    salt            = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode("utf-8")   # store as string in MongoDB


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plain password against a stored bcrypt hash.
    bcrypt.checkpw handles the salt extraction internally.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )

# ---------------- JWT ----------------

def create_access_token(data: dict) -> str:
    """
    Create a signed JWT token.

    Payload example:
        { "sub": "user@email.com", "exp": <timestamp> }

    The token is signed with SECRET_KEY so the server can verify
    it wasn't tampered with on the client side.
    """
    to_encode = data.copy()
    expire    = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)  # type: ignore


def decode_access_token(token: str) -> str:
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail      = "Invalid or expired token",
        headers     = {"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # type: ignore
        email: str = payload.get("sub")  # type: ignore

        if email is None:
            raise credentials_exception

        return email
    except JWTError:
        raise credentials_exception


def verify_access_token(token: str = Depends(oauth2_scheme)) -> str:
    """
    FastAPI dependency — verifies the JWT sent in the Authorization header.

    Usage in a route:
        @app.get("/protected")
        async def protected(user: str = Depends(verify_access_token)):
            return {"user": user}

    Raises 401 if:
        - Token is missing
        - Token signature is invalid
        - Token has expired
        - Token payload has no 'sub' field
    """
    return decode_access_token(token)

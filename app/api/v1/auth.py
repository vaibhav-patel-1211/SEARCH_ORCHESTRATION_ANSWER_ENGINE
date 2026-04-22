from fastapi import APIRouter, HTTPException, status

from schemas.auth_schema import UserSignup, UserLogin, Token
from database.local.client import get_db
from utils.auth_utils import hash_password, verify_password, create_access_token

router = APIRouter(
  prefix ="/v1/auth",
  tags = ["Authentication"]
)

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user: UserSignup):
  db = get_db()
  existing_user = await db.users.find_one({
    "email": user.email
  })

  if existing_user:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

  hashed = hash_password(user.password)
  new_user = {
    "username": user.username,
    "email": user.email,
    "password": hashed
  }
  await db.users.insert_one(new_user)
  return {"message": "User created successfully"}

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
  db = get_db()
  user = await db.users.find_one({"email": user_credentials.email})

  stored_password = user.get("password") if user else None
  if not user or not stored_password or not verify_password(user_credentials.password, stored_password):
    raise HTTPException(status_code=403, detail="Invalid Credentials")

  token = create_access_token(data={"sub": user["email"]})
  return {"access_token": token, "token_type": "bearer"}


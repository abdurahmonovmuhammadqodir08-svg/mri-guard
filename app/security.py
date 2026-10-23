import datetime as dt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from . import config
from .database import get_db, User

ph = PasswordHasher()
bearer = HTTPBearer()


def hash_password(p: str) -> str:
    return ph.hash(p)


def verify_password(hash_: str, p: str) -> bool:
    try:
        return ph.verify(hash_, p)
    except VerifyMismatchError:
        return False


def validate_password_strength(p: str):
    if len(p) < 12 or not any(c.isdigit() for c in p) or not any(c.isalpha() for c in p):
        raise HTTPException(400, "Parol kamida 12 belgi, harf va raqamdan iborat bo'lishi kerak")


def create_access_token(user: User) -> str:
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=config.ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp},
                      config.SECRET_KEY, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(cred.credentials, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token yaroqsiz yoki muddati tugagan")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Foydalanuvchi topilmadi")
    if user.is_active is False:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Hisob bloklangan")
    return user


def require_role(*roles: str):
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Ruxsat yo'q")
        return user
    return checker

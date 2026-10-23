import datetime as dt
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from ..database import get_db, User, audit
from ..security import (hash_password, verify_password, validate_password_strength,
                        create_access_token, current_user)

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


@router.post("/register-patient")
@limiter.limit("5/minute")
def register_patient(request: Request, data: RegisterIn, db: Session = Depends(get_db)):
    """Faqat bemor roli ochiladi. Shifokor/admin hisobini faqat administrator yaratadi."""
    validate_password_strength(data.password)
    if db.query(User).filter_by(email=data.email.lower()).first():
        raise HTTPException(400, "Ro'yxatdan o'tib bo'lmadi")
    u = User(email=data.email.lower(), full_name=data.full_name,
             password_hash=hash_password(data.password), role="patient")
    db.add(u); db.commit()
    audit(db, u.id, "register", ip=request.client.host)
    return {"id": u.id}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, data: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=data.email.lower()).first()
    now = dt.datetime.now(dt.timezone.utc)
    generic = HTTPException(401, "Login yoki parol noto'g'ri")
    if not u:
        raise generic
    if u.locked_until and u.locked_until.replace(tzinfo=dt.timezone.utc) > now:
        raise HTTPException(423, "Hisob vaqtincha bloklangan")
    if not verify_password(u.password_hash, data.password):
        u.failed_logins += 1
        if u.failed_logins >= 5:
            u.locked_until = now + dt.timedelta(minutes=15)
            u.failed_logins = 0
        db.commit()
        audit(db, u.id, "login_failed", ip=request.client.host)
        raise generic
    if u.is_active is False:
        audit(db, u.id, "login_blocked", ip=request.client.host)
        raise HTTPException(403, "Hisob bloklangan. Administratorga murojaat qiling.")
    if u.totp_enabled:
        if not data.totp_code or not pyotp.TOTP(u.totp_secret).verify(data.totp_code, valid_window=1):
            audit(db, u.id, "2fa_failed", ip=request.client.host)
            raise HTTPException(401, "2FA kodi noto'g'ri")
    u.failed_logins = 0
    db.commit()
    audit(db, u.id, "login_ok", ip=request.client.host)
    return {"access_token": create_access_token(u), "token_type": "bearer", "role": u.role}


@router.post("/2fa/setup")
def setup_2fa(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.totp_secret = pyotp.random_base32()
    db.commit()
    uri = pyotp.TOTP(user.totp_secret).provisioning_uri(user.email, issuer_name="MRI-Guard")
    return {"otpauth_uri": uri}


class CodeIn(BaseModel):
    code: str


@router.post("/2fa/enable")
def enable_2fa(data: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(data.code, valid_window=1):
        raise HTTPException(400, "Kod noto'g'ri")
    user.totp_enabled = True
    db.commit()
    audit(db, user.id, "2fa_enabled")
    return {"ok": True}

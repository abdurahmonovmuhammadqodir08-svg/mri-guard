import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import get_db, User, Scan, AuditLog, audit
from ..security import require_role, hash_password, validate_password_strength

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_role("admin")
_ALPHA = "".join(c for c in string.ascii_letters if c not in "lIO") + "23456789"


def temp_password() -> str:
    while True:
        pw = "".join(secrets.choice(_ALPHA) for _ in range(14))
        if any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw):
            return pw


class NewUser(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    password: str | None = None


class ActiveIn(BaseModel):
    active: bool


@router.get("/stats")
def stats(admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    count = lambda role: db.query(func.count(User.id)).filter(User.role == role).scalar()
    return {"doctors": count("doctor"), "patients": count("patient"), "admins": count("admin"),
            "scans": db.query(func.count(Scan.id)).scalar(),
            "attacks": db.query(func.count(Scan.id)).filter(Scan.attack_detected.is_(True)).scalar()}


@router.get("/users")
def users(q: str = "", role: str = "", admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    qs = db.query(User)
    if role in ("doctor", "patient", "admin"):
        qs = qs.filter(User.role == role)
    q = q.strip()[:100]
    if q:
        like = f"%{q}%"
        qs = qs.filter(User.full_name.ilike(like) | User.email.ilike(like))
    return [{"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role,
             "active": u.is_active is not False, "is_self": u.id == admin.id}
            for u in qs.order_by(User.id.desc()).limit(200).all()]


@router.post("/users")
def create_user(data: NewUser, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if data.role not in ("doctor", "patient"):
        raise HTTPException(400, "Rol faqat shifokor yoki bemor bo\u2018lishi mumkin")
    name = data.full_name.strip()
    if not name or len(name) > 255:
        raise HTTPException(400, "F.I.Sh. noto\u2018g\u2018ri")
    email = data.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(400, "Bu e-pochta band")
    pw, temp = data.password, None
    if pw:
        validate_password_strength(pw)
    else:
        pw = temp = temp_password()
    u = User(email=email, full_name=name, password_hash=hash_password(pw), role=data.role)
    db.add(u)
    db.commit()
    audit(db, admin.id, "admin_create_user", f"user={u.id} role={u.role}", request.client.host)
    return {"id": u.id, "temp_password": temp}


@router.post("/users/{uid}/active")
def set_active(uid: int, data: ActiveIn, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Topilmadi")
    if not data.active and u.id == admin.id:
        raise HTTPException(400, "O\u2018zingizni bloklab bo\u2018lmaydi")
    u.is_active = data.active
    db.commit()
    audit(db, admin.id, "admin_activate" if data.active else "admin_block", f"user={u.id}", request.client.host)
    return {"ok": True}


@router.post("/users/{uid}/reset-password")
def reset_password(uid: int, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Topilmadi")
    temp = temp_password()
    u.password_hash = hash_password(temp)
    u.failed_logins = 0
    u.locked_until = None
    db.commit()
    audit(db, admin.id, "admin_reset_password", f"user={u.id}", request.client.host)
    return {"temp_password": temp}


@router.get("/audit")
def audit_log(limit: int = 100, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 500))).all()
    ids = {r.user_id for r in rows if r.user_id}
    emails = {u.id: u.email for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
    return [{"id": r.id, "time": r.created_at.isoformat(), "user": emails.get(r.user_id, ""),
             "action": r.action, "detail": r.detail, "ip": r.ip} for r in rows]

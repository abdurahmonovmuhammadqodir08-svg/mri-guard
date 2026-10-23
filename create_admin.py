"""Super administrator hisobini yaratish. Ishlatish:  python create_admin.py"""
import getpass
import os
os.environ.setdefault("SECRET_KEY", "faqat-hisob-yaratish-uchun-vaqtinchalik-kalit-1234567890")
from app.database import SessionLocal, User
from app.security import hash_password, validate_password_strength

email = input("Administrator e-pochtasi: ").strip().lower()
name = input("F.I.Sh.: ").strip()
pw = getpass.getpass("Parol (kamida 14 belgi, harf va raqam): ")
if len(pw) < 14:
    raise SystemExit("Administrator paroli kamida 14 belgi bo'lishi kerak")
try:
    validate_password_strength(pw)
except Exception as e:
    raise SystemExit(getattr(e, "detail", str(e)))
if pw != getpass.getpass("Parolni takrorlang: "):
    raise SystemExit("Parollar mos kelmadi")
db = SessionLocal()
if db.query(User).filter_by(email=email).first():
    raise SystemExit("Bunday e-pochta allaqachon mavjud")
db.add(User(email=email, full_name=name, password_hash=hash_password(pw), role="admin"))
db.commit()
print("Administrator hisobi yaratildi.")

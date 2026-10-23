"""Shifokor hisobini yaratish (faqat administrator kompyuterida ishga tushiriladi).
Ishlatish:  python create_doctor.py
"""
import getpass
from app.database import Base, engine, SessionLocal, User
from app.security import hash_password, validate_password_strength

Base.metadata.create_all(engine)
email = input("Shifokor e-pochtasi: ").strip().lower()
name = input("F.I.Sh.: ").strip()
pw = getpass.getpass("Parol (kamida 12 belgi, harf va raqam): ")
validate_password_strength(pw)
db = SessionLocal()
if db.query(User).filter_by(email=email).first():
    raise SystemExit("Bunday e-pochta allaqachon mavjud")
db.add(User(email=email, full_name=name, password_hash=hash_password(pw), role="doctor"))
db.commit()
print("Shifokor hisobi yaratildi.")

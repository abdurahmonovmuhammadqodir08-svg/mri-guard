import os
os.environ.setdefault("SECRET_KEY", "faqat-bazaga-yozish-uchun-vaqtinchalik-kalit-1234567890")

from app.database import Base, engine, SessionLocal, User
from app.security import hash_password

Base.metadata.create_all(engine)
db = SessionLocal()
email = "shifokor@test.uz"
user = db.query(User).filter_by(email=email).first()
if user:
    user.password_hash = hash_password("Shifokor2026test")
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    print("Parol yangilandi:", email)
else:
    db.add(User(email=email, full_name="Test Shifokor",
                password_hash=hash_password("Shifokor2026test"), role="doctor"))
    db.commit()
    print("Shifokor qo'shildi:", email)
import datetime as dt
from sqlalchemy import create_engine, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # doctor | patient | admin
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=now, nullable=True)


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    attack_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    detection_score: Mapped[float] = mapped_column(Float, default=0.0)
    purified: Mapped[bool] = mapped_column(Boolean, default=False)
    residual_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="processed")  # processed | needs_review | confirmed
    advice: Mapped[str | None] = mapped_column(Text, nullable=True)  # shifokor maslahati
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def audit(db, user_id, action, detail="", ip=""):
    db.add(AuditLog(user_id=user_id, action=action, detail=detail, ip=ip))
    db.commit()


def ensure_columns():
    """Mavjud bazaga yangi ustunlarni xavfsiz qo'shadi (ALTER TABLE)."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    scan_cols = {c["name"] for c in insp.get_columns("scans")}
    user_cols = {c["name"] for c in insp.get_columns("users")}
    with engine.begin() as conn:
        if "advice" not in scan_cols:
            conn.execute(text("ALTER TABLE scans ADD COLUMN advice TEXT"))
        if "is_active" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        if "created_at" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))


Base.metadata.create_all(engine)
ensure_columns()

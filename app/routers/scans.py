import hashlib, io, secrets, os
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .. import config
from ..database import get_db, Scan, User, audit
from ..security import require_role
from ..ml import pipeline

router = APIRouter(tags=["scans"])
MAGIC = {b"\x89PNG\r\n\x1a\n": "PNG", b"\xff\xd8\xff": "JPEG"}
Image.MAX_IMAGE_PIXELS = 50_000_000  # decompression bomb himoyasi


def sniff(data: bytes):
    for m, name in MAGIC.items():
        if data.startswith(m):
            return name
    return None


@router.post("/scans/upload")
async def upload(request: Request, patient_id: int = Form(...), file: UploadFile = File(...),
                 doctor: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fayl juda katta")
    if not sniff(data):
        raise HTTPException(415, "Faqat PNG/JPEG (DICOM qo'llab-quvvatlash keyingi bosqichda)")
    patient = db.get(User, patient_id)
    if not patient or patient.role != "patient":
        raise HTTPException(404, "Bemor topilmadi")
    try:
        img = Image.open(io.BytesIO(data)); img.verify()
        img = Image.open(io.BytesIO(data)).convert("RGB")  # qayta kodlash: metadata va yashirin kontent tozalanadi
    except Exception:
        raise HTTPException(400, "Tasvir buzilgan")
    try:
        res = pipeline.analyze(img)
    except RuntimeError:
        raise HTTPException(503, "Model hali yuklanmagan")

    clean = io.BytesIO(); img.save(clean, format="PNG")
    sha = hashlib.sha256(clean.getvalue()).hexdigest()
    path = os.path.join(config.STORAGE_DIR, secrets.token_hex(16) + ".png")  # foydalanuvchi nomi ishlatilmaydi
    with open(path, "wb") as f:
        f.write(clean.getvalue())

    scan = Scan(doctor_id=doctor.id, patient_id=patient.id, file_path=path, sha256=sha, **res)
    db.add(scan); db.commit()
    audit(db, doctor.id, "scan_upload",
          f"scan={scan.id} attack={res['attack_detected']} status={res['status']}", request.client.host)
    return {"scan_id": scan.id, **res}


class ConfirmIn(BaseModel):
    advice: str | None = None


@router.post("/scans/{scan_id}/confirm")
def confirm(scan_id: int, request: Request, data: ConfirmIn | None = None,
            doctor: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan or scan.doctor_id != doctor.id:
        raise HTTPException(404, "Topilmadi")
    if scan.status == "needs_review":
        raise HTTPException(409, "Hujum izi to\u2018liq bartaraf etilmadi. Natijani tasdiqlab bo\u2018lmaydi, tasvirni qayta oling.")
    advice = (data.advice or "").strip() if data else ""
    if len(advice) > 2000:
        raise HTTPException(400, "Maslahat matni 2000 belgidan oshmasligi kerak")
    scan.advice = advice or None
    scan.status = "confirmed"; db.commit()
    audit(db, doctor.id, "scan_confirm", f"scan={scan.id} advice_len={len(advice)}", request.client.host)
    return {"ok": True}


@router.get("/patient/results")
def my_results(patient: User = Depends(require_role("patient")), db: Session = Depends(get_db)):
    """Bemor faqat o'z va faqat shifokor tasdiqlagan natijalarini (maslahat bilan) ko'radi."""
    rows = db.query(Scan).filter_by(patient_id=patient.id, status="confirmed").order_by(Scan.id.desc()).all()
    ids = {s.doctor_id for s in rows}
    names = {u.id: u.full_name for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
    return [{"id": s.id, "prediction": s.prediction, "confidence": s.confidence, "advice": s.advice,
             "doctor_name": names.get(s.doctor_id, ""), "date": s.created_at.isoformat()} for s in rows]


@router.get("/doctor/patients")
def list_patients(doctor: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    # TODO: haqiqiy tizimda shifokor faqat o'ziga biriktirilgan bemorlarni ko'rishi kerak
    rows = db.query(User).filter_by(role="patient").order_by(User.full_name).all()
    return [{"id": u.id, "full_name": u.full_name, "email": u.email} for u in rows]


@router.get("/doctor/scans")
def doctor_scans(doctor: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    rows = db.query(Scan).filter_by(doctor_id=doctor.id).order_by(Scan.id.desc()).limit(50).all()
    ids = {s.patient_id for s in rows}
    names = {u.id: u.full_name for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
    return [{"id": s.id, "patient_name": names.get(s.patient_id, "?"), "prediction": s.prediction,
             "confidence": s.confidence, "attack_detected": s.attack_detected, "purified": s.purified,
             "status": s.status, "date": s.created_at.isoformat()} for s in rows]

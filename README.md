# MRI-Guard (magistrlik dissertatsiyasi loyihasi)

## Ishga tushirish
    python -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env     # SECRET_KEY ni almashtiring
    export $(grep -v '^#' .env | xargs)
    uvicorn app.main:app --reload

## Model
Colab'da o'qitilgan modelni `torch.jit.save` bilan saqlab, `models/brain_tumor.pt` ga qo'ying.

## Keyingi bosqichlar
1. Colab notebook: klassifikator o'qitish + FGSM/PGD/C&W hujumlari + detektor baholash
2. Frontend (shifokor va bemor panellari)
3. DICOM qo'llab-quvvatlash, admin paneli, Docker + Nginx (HTTPS)

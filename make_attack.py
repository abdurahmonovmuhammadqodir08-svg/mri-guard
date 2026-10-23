import os, sys
os.environ.setdefault("SECRET_KEY", "faqat-sinov-uchun-vaqtinchalik-kalit-1234567890")
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from app.ml import pipeline as P

SRC = sys.argv[1] if len(sys.argv) > 1 else "Sinov.jpg"
OUT = "hujum_rasmlar"
os.makedirs(OUT, exist_ok=True)

if not P.load_model():
    sys.exit("Model yuklanmadi (models/brain_tumor.pt ni tekshiring)")

# Sayt bilan bir xil tayyorlash: kulrang, 224x224. Hujum bitta kanalda quriladi,
# shunda sayt kulrangga o'tkazganda hujum izi yo'qolmaydi.
base = Image.open(SRC).convert("L").resize((224, 224), Image.BILINEAR)
x0 = torch.from_numpy(np.asarray(base, dtype=np.float32) / 255.0).view(1, 1, 224, 224)


def f(x1):
    return P._model(x1.repeat(1, 3, 1, 1))


def pgd(x, y, eps, steps=40):
    alpha = 2.5 * eps / steps
    xa = (x + torch.empty_like(x).uniform_(-eps, eps)).clamp(0, 1)
    for _ in range(steps):
        xa.requires_grad_(True)
        g = torch.autograd.grad(F.cross_entropy(f(xa), y), xa)[0]
        xa = xa.detach() + alpha * g.sign()
        xa = torch.min(torch.max(xa, x - eps), x + eps).clamp(0, 1)
    return xa.detach()


with torch.no_grad():
    p0 = F.softmax(f(x0), 1)[0]
y = p0.argmax().view(1)
print(f"Toza tasvir: {P._classes[int(y)]} ({float(p0.max()):.1%})\n")

for k in (4, 8, 16, 32):
    xa = pgd(x0, y, k / 255)
    arr = (xa[0, 0].numpy() * 255).round().astype(np.uint8)  # PNG kabi yo'qotishsiz saqlash
    path = os.path.join(OUT, f"hujum_pgd_{k}.png")
    Image.fromarray(arr, mode="L").save(path)
    r = P.analyze(Image.open(path))
    with torch.no_grad():
        raw = F.softmax(f(torch.from_numpy(arr.astype(np.float32) / 255).view(1, 1, 224, 224)), 1)[0]
    fooled = int(raw.argmax()) != int(y)
    print(f"=== PGD eps={k}/255  ->  {path}")
    print(f"  Himoyasiz model: {P._classes[int(raw.argmax())]} ({float(raw.max()):.1%})  {'ALDANDI' if fooled else 'aldanmadi'}")
    print(f"  Sayt: hujum={r['attack_detected']} ball={r['detection_score']:.3f} "
          f"tozalandi={r['purified']} qolgan={r['residual_score']}")
    print(f"  Sayt xulosasi: {r['prediction']} ({r['confidence']:.1%}), holat={r['status']}\n")
"""Pipeline'ni sinash: toza tasvir va PGD bilan hujumlangan tasvir (web-serversiz).
Ishlatish:  python test_pipeline.py rasm.jpg
"""
import sys
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from app.ml import pipeline as P


def pgd(model, x, y, eps, steps=20):
    alpha = 2.5 * eps / steps
    xa = (x + torch.empty_like(x).uniform_(-eps, eps)).clamp(0, 1)
    for _ in range(steps):
        xa.requires_grad_(True)
        g = torch.autograd.grad(F.cross_entropy(model(xa), y), xa)[0]
        xa = xa.detach() + alpha * g.sign()
        xa = torch.min(torch.max(xa, x - eps), x + eps).clamp(0, 1)
    return xa.detach()


def show(title, r):
    print(f"\n--- {title} ---")
    print(f"  Bashorat: {r['prediction']} ({r['confidence']:.1%})")
    print(f"  Hujum aniqlandimi: {r['attack_detected']} (ball: {r['detection_score']:.3f})")
    if r["purified"]:
        print(f"  Tozalandi, qolgan ball: {r['residual_score']:.3f}")
    print(f"  Holat: {r['status']}")


if not P.load_model():
    sys.exit("Model yuklanmadi")
img = Image.open(sys.argv[1])
clean = P.analyze(img)
show("TOZA tasvir", clean)

x = torch.from_numpy(P._to_array(img).transpose(2, 0, 1).copy()).unsqueeze(0)
y = torch.tensor([P._classes.index(clean["prediction"])])
for k in (2, 8):
    xa = pgd(P._model, x, y, k / 255)
    arr = (xa[0].numpy().transpose(1, 2, 0) * 255).round().astype(np.uint8)
    raw = P._classes[int(P._predict_proba(arr.astype(np.float32) / 255).argmax())]
    print(f"\n=== PGD hujumi, eps={k}/255 ===")
    print(f"  Himoyasiz model javobi: {raw}")
    show(f"HUJUMLANGAN tasvir (eps={k}/255), himoya bilan", P.analyze(Image.fromarray(arr)))

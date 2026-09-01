import json
import random
from pathlib import Path

import numpy as np
import torch


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_pos_weight(labels) -> float:
    positives = sum(float(label) > 0 for label in labels)
    negatives = sum(float(label) == 0 for label in labels)
    if positives == 0:
        raise ValueError("training split has no positive windows")
    return negatives / positives


def train_one_batch(model, optimizer, x, y, pos_weight: float) -> float:
    if x.ndim != 3 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("x must be (batch, channels, time) and y must be (batch,)")
    model.train()
    optimizer.zero_grad(set_to_none=True)
    logits = model(x)
    loss = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(pos_weight, dtype=logits.dtype, device=logits.device)
    )(logits, y.to(dtype=logits.dtype))
    loss.backward()
    optimizer.step()
    return float(loss.detach().cpu())


def save_checkpoint(
    path: Path,
    model,
    optimizer,
    config,
    split_manifest,
    stats,
    epoch,
    metrics,
    seed: int | None = None,
) -> None:
    payload = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "config": config,
        "split_manifest": split_manifest,
        "stats": stats,
        "epoch": epoch,
        "metrics": metrics,
        "seed": seed,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

import argparse
import json

import torch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()

    cuda_ok = bool(torch.cuda.is_available())
    report = {
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": cuda_ok,
        "device_count": torch.cuda.device_count() if cuda_ok else 0,
        "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        if cuda_ok
        else [],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_cuda and not cuda_ok:
        raise SystemExit("CUDA is required but torch.cuda.is_available() is false")

    device = torch.device("cuda" if cuda_ok else "cpu")
    model = torch.nn.Linear(4, 1).to(device)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    for _ in range(args.steps):
        x = torch.ones(2, 4, device=device)
        y = torch.ones(2, 1, device=device)
        optimizer.zero_grad(set_to_none=True)
        loss = torch.nn.functional.mse_loss(model(x), y)
        loss.backward()
        optimizer.step()
    print(f"SMOKE_PASS device={device} steps={args.steps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

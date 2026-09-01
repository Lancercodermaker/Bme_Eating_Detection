# 智能手表进食检测基线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Windows 的 `E:\bme_compitition` 中建立一个不修改原始数据、按 participant 隔离、可复现的智能手表进食事件检测基线，先完成数据→标签→训练→事件评估闭环，再以验证证据决定是否加入 PPG 和高级时序模块。

**Architecture:** 采用 `src` 布局，把流式文件解析、时间轴恢复/重采样、标签、participant split、窗口数据集、事件解码/指标、模型和训练循环分成独立模块。原始数据只通过 CLI/config 读取，生成的审计报告、缓存、权重和实验结果统一写入 Git 忽略目录；所有模型共用同一套事件解码和 IoU 评估。

**Tech Stack:** Windows PowerShell、独立 Conda 环境、Python 3.11、NumPy、pandas、SciPy、PyYAML、PyTorch、pytest、scikit-learn（仅用于需要时的简单工具）。PyTorch CUDA 安装命令按执行当日官方选择结果确定，并把实际版本导出保存。

---

## 0. 当前事实、矛盾和执行边界

本计划以以下材料和本地检查结果为事实来源，不重复已经完成的广泛领域搜索：

- 设计文档：`E:\bme_compitition\docs\superpowers\specs\2026-08-31-smartwatch-eating-detection-baseline-design.md`。
- 接续摘要：`E:\bme_compitition\handoff-summary.md`。
- Git 根目录：`E:\bme_compitition`；当前分支为 `master`，工作区检查时干净。
- 训练数据根目录：`E:\bme_compitition\official_test_dataset\Data\02_traindataset`；索引/元数据目录为 `E:\bme_compitition\official_test_dataset\Data\01_dataset`。
- `DataTable.txt` 显示餐段表字段为 `beforeTime/afterTime/dietaryHand/wearHand`，传感器表包含 `ACC_TIME/PPG_TIME/GYRO_TIME`、`PPG1`–`PPG44` 和 6 轴 IMU。
- 已抽查的传感器文件为制表符分隔；首行存在 `PPG_TIME=0`、全零 PPG、有效 IMU 的组合，故不能把一行简单视为三种流都有效。
- 本地原始训练数据约 93 GB，只能流式/分段处理；测试目录不能参与训练或模型选择。

发现的具体矛盾是：handoff 摘要写“最新提交为 `5fcdfe2`”，但实际 `git log` 的 `HEAD` 是 `b616ddf (docs: add handoff package for implementation)`。最小安全假设是：摘要描述的设计决定仍然有效，但 Git 历史以实际 `HEAD` 和工作区为准；执行第一步保存实际 commit，之后不重写历史。

已按仓库规则使用 Context7：先 resolve 再 query，选用 PyTorch `/pytorch/pytorch`、SciPy `/scipy/scipy`、pandas `/websites/pandas_pydata` 和 Conda `/conda/conda`。计划据此固定以下工程边界：

- `Conv1d` 的输入统一为 `(batch, channels, time)`；M0 不在 loss 前手动 sigmoid。
- `BCEWithLogitsLoss(pos_weight=...)` 的 `pos_weight` 只由训练集统计，验证集只调阈值和后处理。
- pandas 使用 `read_csv(..., sep="\t", usecols=..., chunksize=...)` 流式解析大文件。
- SciPy 的 `resample_poly` 只对已恢复为统一时间轴的数据使用；滤波优先 SOS，并记录边界策略。
- Conda 使用独立环境；可共享 YAML 用 `--from-history`，同平台精确复现另外保存显式导出。

## 1. 文件地图与职责

下列文件是本计划中唯一的代码职责边界。执行时按任务创建；每个任务只修改列出的文件及其测试。

| 文件 | 职责 | 是否写入原始数据 |
|---|---|---|
| `environment.yml` | Conda 可共享环境声明；基础 Python/科学计算/测试依赖，不把 93 GB 数据放入环境 | 否 |
| `environment-win-64.lock.yml` | 执行机器实际安装后的 Windows 锁定导出，记录可复现版本 | 否 |
| `pyproject.toml` | `src` 包安装、CLI 入口、pytest 默认配置 | 否 |
| `configs/m0_p0.yaml` | M0+P0 的唯一默认配置，路径可由 CLI 覆盖 | 否 |
| `configs/m1_imu_ppg.yaml` | 只有 M0 通过后启用的 M1 配置 | 否 |
| `scripts/verify_environment.py` | NVIDIA/PyTorch/CUDA 可见性和极小 GPU/CPU 训练 smoke test | 否 |
| `src/eating_detection/config.py` | YAML 与 CLI 合并、路径解析、类型/范围校验 | 否 |
| `src/eating_detection/io.py` | 元数据读取、participant canonicalization、传感器分块解析、时间戳/质量 mask | 否 |
| `src/eating_detection/audit.py` | 小样本或流式全量审计，输出 JSON/CSV 统计，不缓存原始数组 | 否 |
| `src/eating_detection/timebase.py` | 去除无效时间戳、重复时间戳聚合、统一时间轴和间隙 mask | 否 |
| `src/eating_detection/preprocess.py` | 抗混叠重采样、IMU/PPG 特征、训练集标准化统计和可回退消融 | 否 |
| `src/eating_detection/labels.py` | 餐段清洗、滑动窗口生成、硬/软/忽略边界标签 | 否 |
| `src/eating_detection/splits.py` | participant 分组划分、manifest 保存、交叉检查 | 否 |
| `src/eating_detection/dataset.py` | 窗口索引、按需读取/缓存、PyTorch Dataset 和 participant batch sampler | 否 |
| `src/eating_detection/metrics.py` | 区间 IoU、一次性匹配、事件 Precision/Recall/F1、start/end MAE | 否 |
| `src/eating_detection/decoding.py` | 概率阈值、hysteresis、连续段合并、短段删除和验证集调参 | 否 |
| `src/eating_detection/models.py` | M0 IMU 1D CNN、M1 独立 PPG encoder 与融合 | 否 |
| `src/eating_detection/training.py` | seed、pos_weight、训练/验证循环、checkpoint 和窗口概率输出 | 否 |
| `src/eating_detection/cli.py` | `audit`、`make-manifest`、`train`、`evaluate` 命令编排；不承载业务实现 | 否 |
| `tests/conftest.py` | 只在临时目录生成几行 toy sensor/meal 数据，不提交竞赛数据 | 否 |
| `tests/test_config.py` | 配置覆盖、路径和非法参数测试 | 否 |
| `tests/test_io.py` | 分隔符、分块读取、timestamp 0、PPG 全零和 participant ID 测试 | 否 |
| `tests/test_audit.py` | 小样本审计报告字段和不全量加载测试 | 否 |
| `tests/test_timebase.py` | 重复包、无效时间、统一时间轴和 mask 测试 | 否 |
| `tests/test_preprocess.py` | 重采样长度、标准化只用训练统计和 P0/P1 回退测试 | 否 |
| `tests/test_labels.py` | 正常/反序/相同端点、窗口 overlap、软边界测试 | 否 |
| `tests/test_splits.py` | participant 无交叉、确定性和 test 排除测试 | 否 |
| `tests/test_dataset.py` | 窗口 shape、mask 保留、participant batch 不混组测试 | 否 |
| `tests/test_metrics.py` | IoU 严格阈值、一次性匹配、空预测/空真值和 MAE 测试 | 否 |
| `tests/test_decoding.py` | 阈值/hysteresis/合并/短段和验证集调参隔离测试 | 否 |
| `tests/test_training.py` | 一批 CPU 训练和 loss/logit 形状 smoke test | 否 |
| `tests/test_models.py` | M0/M1 输入输出 shape 和缺失模态 mask 测试 | 否 |
| `README.md` | Windows 环境、sample smoke、完整运行、输出解释和复现规则 | 否 |

所有生成物只写入 `artifacts/`、`cache/`、`checkpoints/` 或 `outputs/`。这些目录已经被 `.gitignore` 忽略；若新增日志或锁文件目录，先补 `.gitignore`，再运行生成命令。

## 2. 阶段一：环境与数据闭环

### Task 1: 建立独立工程入口和 Conda 环境

**Files:**

- Create: `pyproject.toml`
- Create: `environment.yml`
- Create: `scripts/verify_environment.py`
- Create: `src/eating_detection/__init__.py`
- Create: `tests/test_config.py`
- Test: `scripts/verify_environment.py` 的命令行 smoke；`pytest` 测试

选择链：Windows + RTX 5060 Laptop + 约 8 GB 显存 → base 环境和系统 Python 污染会让失败原因不可分离 → 独立 Conda 环境并先做最小 GPU 运算 → 以 `torch.cuda.is_available()`、设备名、CUDA 版本和两步反向传播作为环境验收。

- [ ] **Step 1: 先写配置和最小训练的失败测试**

```python
# tests/test_config.py
from pathlib import Path

import pytest

from eating_detection.config import load_config


def test_cli_path_overrides_yaml(tmp_path: Path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        "data_root: old\nresample_hz: 25\nwindow_sec: 15\nstep_sec: 3\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file, data_root=tmp_path / "data", resample_hz=16)
    assert cfg.data_root == tmp_path / "data"
    assert cfg.resample_hz == 16
    assert cfg.window_sec == 15


def test_invalid_window_is_rejected(tmp_path: Path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text("window_sec: 2\nstep_sec: 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="step_sec"):
        load_config(cfg_file)
```

- [ ] **Step 2: 运行失败测试，确认缺失模块而不是静默通过**

Run:

```powershell
python -m pytest tests/test_config.py -q
```

Expected: FAIL，错误集中为 `ModuleNotFoundError: No module named 'eating_detection'` 或 `load_config` 尚未定义。

- [ ] **Step 3: 写最小包入口、配置类型和 pyproject**

```python
# src/eating_detection/__init__.py
__version__ = "0.1.0"
```

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "smartwatch-eating-detection"
version = "0.1.0"
description = "Participant-grouped smartwatch eating event baseline"
requires-python = ">=3.11,<3.13"
dependencies = [
  "numpy>=2.0,<3",
  "pandas>=2.2,<3",
  "scipy>=1.14,<2",
  "PyYAML>=6,<7",
]

[project.optional-dependencies]
dev = ["pytest>=8,<9"]

[project.scripts]
eating-detection = "eating_detection.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

```python
# src/eating_detection/config.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Config:
    data_root: Path
    index_dir: Path
    train_dir: Path
    output_dir: Path
    resample_hz: int = 25
    window_sec: int = 15
    step_sec: int = 3
    seed: int = 7


def load_config(path: Path, **overrides: Any) -> Config:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw.update({k: v for k, v in overrides.items() if v is not None})
    data_root = Path(raw["data_root"])
    cfg = Config(
        data_root=data_root,
        index_dir=Path(raw.get("index_dir", data_root / "01_dataset")),
        train_dir=Path(raw.get("train_dir", data_root / "02_traindataset")),
        output_dir=Path(raw.get("output_dir", "artifacts")),
        resample_hz=int(raw.get("resample_hz", 25)),
        window_sec=int(raw.get("window_sec", 15)),
        step_sec=int(raw.get("step_sec", 3)),
        seed=int(raw.get("seed", 7)),
    )
    if cfg.resample_hz not in {15, 16, 25, 50}:
        raise ValueError("resample_hz must be one of 15, 16, 25, 50")
    if cfg.window_sec <= 0 or cfg.step_sec <= 0 or cfg.step_sec > cfg.window_sec:
        raise ValueError("step_sec must be positive and no greater than window_sec")
    return cfg
```

`data_root` 必须由 YAML 或 CLI 提供；训练逻辑中不出现任何 `E:\...` 字面量。

- [ ] **Step 4: 写环境声明和验证脚本**

```yaml
# environment.yml
name: smartwatch-eating
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - numpy
  - pandas
  - scipy
  - pyyaml
  - pytest
  - scikit-learn
  - pip:
      - -e .
```

```python
# scripts/verify_environment.py
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
        if cuda_ok else [],
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
```

安装顺序必须是：先执行 `nvidia-smi` 保存驱动信息；再执行 `conda create --name smartwatch-eating python=3.11 pip -y`；激活后按执行当日 Context7/官方 PyTorch 安装选择安装 CUDA wheel；然后 `python -m pip install -e ".[dev]"`。PyTorch 的 CUDA 变体不凭记忆写进命令；安装后运行 `conda export --name smartwatch-eating --format=environment-yaml --file environment-win-64.lock.yml`，把真实版本纳入仓库。

- [ ] **Step 5: 创建环境并验证 GPU；环境失败时停止进入数据实现**

Run:

```powershell
conda --version
nvidia-smi
conda create --name smartwatch-eating python=3.11 pip -y
conda activate smartwatch-eating
python -m pip install -e ".[dev]"
python scripts/verify_environment.py --steps 2 --require-cuda
```

Expected: `nvidia-smi` 显示 RTX 5060 Laptop；脚本 JSON 中 `cuda_available` 为 `true`，最后出现 `SMOKE_PASS device=cuda steps=2`。如果机器没有可见 GPU，使用不带 `--require-cuda` 的 CPU smoke 只验证闭环，并在报告中明确记录，不能把 CPU 结果冒充 GPU 验收。

- [ ] **Step 6: 导出实际环境锁文件，运行测试并提交环境入口**

Run:

```powershell
conda export --name smartwatch-eating --format=environment-yaml --file environment-win-64.lock.yml
python -m pytest tests/test_config.py -q
```

Expected: 配置测试通过；`environment-win-64.lock.yml` 记录当前 Windows 环境的实际版本。PyTorch 安装失败时不提交一个虚假的锁文件，先修复环境并重新导出。

Commit:

```powershell
git add pyproject.toml environment.yml environment-win-64.lock.yml scripts/verify_environment.py src/eating_detection/__init__.py src/eating_detection/config.py tests/test_config.py
git commit -m "build: add isolated environment and project entrypoint"
```

### Task 2: 流式解析和小样本数据审计

**Files:**

- Modify: `src/eating_detection/config.py`
- Create: `src/eating_detection/io.py`
- Create: `src/eating_detection/audit.py`
- Create: `src/eating_detection/cli.py`
- Create: `configs/m0_p0.yaml`
- Create: `tests/conftest.py`
- Create: `tests/test_io.py`
- Create: `tests/test_audit.py`

选择链：原始文件大、sensor streams 异步、PPG 全零和 timestamp 0 共存 → 一次性 `read_csv` 会占用不可控内存且掩盖流有效性 → pandas 官方支持 chunksize 迭代 → parser 只读所需列并为每块返回质量统计；首轮只读两个文件/每文件最多 2000 行。

- [ ] **Step 1: 写失败测试和 toy fixture**

```python
# tests/conftest.py
import pytest


@pytest.fixture
def toy_sensor_file(tmp_path):
    path = tmp_path / "sensor.txt"
    ppg_columns = [f"PPG{i}" for i in range(1, 45)]
    header = ["ACC_TIME", "PPG_TIME", "GYRO_TIME", *ppg_columns,
              "ACC_X", "ACC_Y", "ACC_Z", "GYRO_X", "GYRO_Y", "GYRO_Z"]
    rows = [
        [0, 0, 1000, *([0] * 44), 1, 2, 3, 4, 5, 6],
        [1000, 0, 1000, *([0] * 44), 2, 3, 4, 5, 6, 7],
        [1000, 1100, 1000, *([10] * 44), 3, 4, 5, 6, 7, 8],
    ]
    text = "\n".join("\t".join(map(str, row)) for row in [header, *rows]) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
```

```python
# tests/test_io.py
from eating_detection.io import canonical_participant_id, iter_sensor_chunks


def test_timestamp_zero_and_ppg_zero_are_masked(toy_sensor_file):
    chunks = list(iter_sensor_chunks(toy_sensor_file, chunksize=2))
    assert len(chunks) == 2
    first = chunks[0]
    assert first.acc_valid.tolist() == [False, True]
    assert first.gyro_valid.tolist() == [True, True]
    assert first.ppg_valid.tolist() == [False, False]
    assert canonical_participant_id(" HNU 21013 ") == "hnu21013"
```

```python
# tests/test_audit.py
from eating_detection.audit import audit_sensor_files


def test_audit_is_bounded_and_reports_quality(toy_sensor_file):
    report = audit_sensor_files([toy_sensor_file], max_rows=2, chunksize=1)
    assert report["files_read"] == 1
    assert report["rows_read"] == 2
    assert report["timestamp_zero_rows"] >= 1
    assert report["ppg_invalid_rows"] == 2
```

- [ ] **Step 2: 运行目标测试确认 parser 尚不存在**

Run:

```powershell
python -m pytest tests/test_io.py tests/test_audit.py -q
```

Expected: FAIL with missing `eating_detection.io`/`audit` symbols。

- [ ] **Step 3: 实现分块 parser，不把 chunk 拼成全文件数组**

```python
# src/eating_detection/io.py
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SensorChunk:
    timestamp_ms: np.ndarray
    acc: np.ndarray
    gyro: np.ndarray
    ppg: np.ndarray
    acc_valid: np.ndarray
    gyro_valid: np.ndarray
    ppg_valid: np.ndarray


def canonical_participant_id(raw: str) -> str:
    return re.sub(r"\s+", "", str(raw).strip().casefold())


def iter_sensor_chunks(path: Path, chunksize: int = 50_000) -> Iterator[SensorChunk]:
    ppg_cols = [f"PPG{i}" for i in range(1, 45)]
    usecols = ["ACC_TIME", "PPG_TIME", "GYRO_TIME", *ppg_cols,
               "ACC_X", "ACC_Y", "ACC_Z", "GYRO_X", "GYRO_Y", "GYRO_Z"]
    numeric = {col: "float32" for col in usecols if not col.endswith("_TIME")}
    numeric.update({"ACC_TIME": "Int64", "PPG_TIME": "Int64", "GYRO_TIME": "Int64"})
    for frame in pd.read_csv(path, sep="\t", usecols=usecols, dtype=numeric,
                             chunksize=chunksize):
        acc_time = frame["ACC_TIME"].fillna(0).to_numpy(np.int64)
        gyro_time = frame["GYRO_TIME"].fillna(0).to_numpy(np.int64)
        ppg_time = frame["PPG_TIME"].fillna(0).to_numpy(np.int64)
        acc = frame[["ACC_X", "ACC_Y", "ACC_Z"]].to_numpy(np.float32)
        gyro = frame[["GYRO_X", "GYRO_Y", "GYRO_Z"]].to_numpy(np.float32)
        ppg = frame[ppg_cols].to_numpy(np.float32)
        acc_valid = (acc_time > 0) & np.isfinite(acc).all(axis=1)
        gyro_valid = (gyro_time > 0) & np.isfinite(gyro).all(axis=1)
        ppg_valid = (ppg_time > 0) & np.isfinite(ppg).all(axis=1) & (np.abs(ppg).sum(axis=1) > 0)
        yield SensorChunk(
            timestamp_ms=np.column_stack([acc_time, ppg_time, gyro_time]),
            acc=acc, gyro=gyro, ppg=ppg,
            acc_valid=acc_valid, gyro_valid=gyro_valid, ppg_valid=ppg_valid,
        )
```

每块保留三列时间戳而不是假设同一 timestamp；时间轴模块会分别处理三个流。PPG 的全零判定只影响 `ppg_valid`，不会删除原始 PPG 数值。

- [ ] **Step 4: 实现审计聚合和 CLI sample 模式**

```python
# src/eating_detection/audit.py
from pathlib import Path
from typing import Iterable

from .io import iter_sensor_chunks


def audit_sensor_files(paths: Iterable[Path], max_rows: int | None = None,
                       chunksize: int = 50_000) -> dict[str, int]:
    report = {"files_read": 0, "rows_read": 0, "timestamp_zero_rows": 0,
              "ppg_invalid_rows": 0, "acc_invalid_rows": 0, "gyro_invalid_rows": 0}
    for path in sorted(paths):
        report["files_read"] += 1
        remaining = max_rows
        for chunk in iter_sensor_chunks(path, chunksize=chunksize):
            take = len(chunk.acc) if remaining is None else min(len(chunk.acc), remaining)
            report["rows_read"] += take
            report["timestamp_zero_rows"] += int((chunk.timestamp_ms[:take] == 0).any(axis=1).sum())
            report["ppg_invalid_rows"] += int((~chunk.ppg_valid[:take]).sum())
            report["acc_invalid_rows"] += int((~chunk.acc_valid[:take]).sum())
            report["gyro_invalid_rows"] += int((~chunk.gyro_valid[:take]).sum())
            if remaining is not None:
                remaining -= take
                if remaining <= 0:
                    break
    return report
```

CLI `audit` 必须只接收 `--index-dir`、`--train-dir`、`--output-dir`、`--limit-files`、`--max-rows` 等参数，调用 parser 后把 `audit_sample.json` 写进 output-dir，并打印 `AUDIT_PASS files=... rows=...`。路径由调用者传入，不在 CLI 逻辑内写绝对路径。

```yaml
# configs/m0_p0.yaml
data_root: official_test_dataset/Data
output_dir: artifacts/m0_p0
resample_hz: 25
window_sec: 15
step_sec: 3
seed: 7
chunksize: 50000
label_positive_overlap: 0.25
boundary_mode: soft
event_iou_threshold: 0.25
```

- [ ] **Step 5: 先只读少量真实数据，确认报告可解释**

Run:

```powershell
python -m eating_detection audit --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" --output-dir "artifacts\audit\sample" --limit-files 2 --max-rows 2000
```

Expected: 进程成功结束并打印 `AUDIT_PASS`；`artifacts\audit\sample\audit_sample.json` 包含 `files_read=2`、`rows_read<=4000`、三类 invalid 计数和重复 timestamp 字段。不能出现 93 GB 全量缓存文件。

- [ ] **Step 6: 运行测试并提交**

Run:

```powershell
python -m pytest tests/test_io.py tests/test_audit.py -q
```

Expected: 所有目标测试 PASS。

Commit:

```powershell
git add src/eating_detection/io.py src/eating_detection/audit.py src/eating_detection/cli.py src/eating_detection/config.py configs/m0_p0.yaml tests/conftest.py tests/test_io.py tests/test_audit.py
git commit -m "feat: add streaming sensor parser and bounded audit"
```

### Task 3: 恢复时间轴、重采样并生成质量 mask

**Files:**

- Create: `src/eating_detection/timebase.py`
- Create: `src/eating_detection/preprocess.py`
- Create: `tests/test_timebase.py`
- Create: `tests/test_preprocess.py`
- Modify: `src/eating_detection/io.py`

选择链：重复包不能当成等间隔采样点；timestamp 0 不能插值成真实观测；降采样可能混叠 → 先按每个 stream 去无效时间、稳定排序、重复 timestamp 聚合，再在统一时间轴上插值并用 `resample_poly` 做目标频率转换；P0 保留原始标准化通道和 mask，P1 滤波只作为可回退开关。

- [ ] **Step 1: 写时间轴和标准化失败测试**

```python
# tests/test_timebase.py
import numpy as np

from eating_detection.timebase import canonicalize_stream, infer_rate_hz


def test_zero_timestamps_removed_and_duplicates_averaged():
    t = np.array([0, 1000, 1000, 2000], dtype=np.int64)
    x = np.array([[99.0], [1.0], [3.0], [5.0]], dtype=np.float32)
    out = canonicalize_stream(t, x)
    assert out.timestamps_ms.tolist() == [1000, 2000]
    assert np.allclose(out.values[:, 0], [2.0, 5.0])
    assert out.duplicate_rows == 1


def test_rate_uses_positive_unique_deltas():
    assert infer_rate_hz(np.array([1000, 1020, 1040, 1060])) == 50.0
```

```python
# tests/test_preprocess.py
import numpy as np

from eating_detection.preprocess import fit_standardizer, imu_features


def test_imu_features_keep_raw_magnitudes_and_two_masks():
    acc = np.array([[3, 0, 0], [0, 4, 0]], dtype=np.float32)
    gyro = np.array([[0, 0, 2], [0, 0, 0]], dtype=np.float32)
    acc_ok = np.array([True, False])
    gyro_ok = np.array([True, True])
    features, mask = imu_features(acc, gyro, acc_ok, gyro_ok)
    assert features.shape == (2, 8)
    assert np.allclose(features[:, 6], [3, 4])
    assert mask.tolist() == [[True, True], [False, True]]


def test_standardizer_uses_train_values_only():
    stats = fit_standardizer(np.array([[1.0, 10.0], [3.0, 14.0]]), np.ones((2, 2), bool))
    assert np.allclose(stats.mean, [2.0, 12.0])
    assert np.allclose(stats.std, [1.0, 2.0])
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
python -m pytest tests/test_timebase.py tests/test_preprocess.py -q
```

Expected: FAIL，因为 `timebase.py` 和 `preprocess.py` 还不存在。

- [ ] **Step 3: 实现 timestamp-domain canonicalization 和统一插值接口**

```python
# src/eating_detection/timebase.py
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class CanonicalStream:
    timestamps_ms: np.ndarray
    values: np.ndarray
    duplicate_rows: int


def canonicalize_stream(timestamps_ms: np.ndarray, values: np.ndarray) -> CanonicalStream:
    t = np.asarray(timestamps_ms, dtype=np.int64)
    x = np.asarray(values, dtype=np.float32)
    valid = (t > 0) & np.isfinite(x).all(axis=1)
    t, x = t[valid], x[valid]
    order = np.argsort(t, kind="stable")
    t, x = t[order], x[order]
    unique, inverse, counts = np.unique(t, return_inverse=True, return_counts=True)
    out = np.zeros((len(unique), x.shape[1]), dtype=np.float32)
    for i in range(len(unique)):
        out[i] = x[inverse == i].mean(axis=0)
    return CanonicalStream(unique, out, int(len(t) - len(unique)))


def infer_rate_hz(timestamps_ms: np.ndarray) -> float:
    t = np.unique(np.asarray(timestamps_ms, dtype=np.int64))
    dt = np.diff(t)
    dt = dt[dt > 0]
    if len(dt) == 0:
        raise ValueError("at least two positive timestamps are required")
    return float(1000.0 / np.median(dt))


def interpolate_uniform(stream: CanonicalStream, rate_hz: float,
                        start_ms: int, end_ms: int, max_gap_ms: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    grid = np.arange(start_ms, end_ms + 0.5 * 1000 / rate_hz, 1000 / rate_hz)
    values = np.column_stack([np.interp(grid, stream.timestamps_ms, stream.values[:, j])
                              for j in range(stream.values.shape[1])])
    left = np.searchsorted(stream.timestamps_ms, grid, side="right") - 1
    right = np.clip(left + 1, 0, len(stream.timestamps_ms) - 1)
    left = np.clip(left, 0, len(stream.timestamps_ms) - 1)
    gap = stream.timestamps_ms[right] - stream.timestamps_ms[left]
    valid = (grid >= stream.timestamps_ms[0]) & (grid <= stream.timestamps_ms[-1]) & (gap <= max_gap_ms)
    return grid.astype(np.int64), values.astype(np.float32), valid
```

`interpolate_uniform` 在 stream 间共享 `start_ms/end_ms`，但每个 stream 独立生成 `valid`。端点外和过大间隙不标 valid，即使 `np.interp` 产生了数值，也必须由 mask 屏蔽。

- [ ] **Step 4: 实现抗混叠重采样、IMU P0 特征和训练统计**

```python
# src/eating_detection/preprocess.py
from dataclasses import dataclass
from fractions import Fraction
import numpy as np
from scipy import signal


@dataclass(frozen=True)
class Standardizer:
    mean: np.ndarray
    std: np.ndarray


def resample_uniform(values: np.ndarray, source_hz: float, target_hz: int) -> np.ndarray:
    ratio = Fraction(target_hz / source_hz).limit_denominator(1000)
    return signal.resample_poly(values, ratio.numerator, ratio.denominator, axis=0).astype(np.float32)


def fit_standardizer(values: np.ndarray, valid: np.ndarray) -> Standardizer:
    x = np.asarray(values, dtype=np.float32)
    ok = np.asarray(valid, dtype=bool)
    mean = np.zeros(x.shape[1], dtype=np.float32)
    std = np.ones(x.shape[1], dtype=np.float32)
    for j in range(x.shape[1]):
        col = x[ok[:, j], j] if ok.ndim == 2 else x[ok, j]
        if len(col) == 0:
            raise ValueError(f"channel {j} has no valid training samples")
        mean[j] = col.mean()
        std[j] = max(float(col.std()), 1e-6)
    return Standardizer(mean, std)


def imu_features(acc: np.ndarray, gyro: np.ndarray, acc_valid: np.ndarray,
                 gyro_valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    acc = np.asarray(acc, np.float32)
    gyro = np.asarray(gyro, np.float32)
    features = np.column_stack([acc, gyro, np.linalg.norm(acc, axis=1),
                                 np.linalg.norm(gyro, axis=1)])
    mask = np.column_stack([acc_valid, gyro_valid]).astype(bool)
    return features.astype(np.float32), mask


def apply_standardizer(values: np.ndarray, stats: Standardizer) -> np.ndarray:
    return ((values - stats.mean) / stats.std).astype(np.float32)


def lowpass_sos(values: np.ndarray, cutoff_hz: float, sample_hz: int) -> np.ndarray:
    sos = signal.butter(4, cutoff_hz, btype="lowpass", fs=sample_hz, output="sos")
    if len(values) < 32:
        raise ValueError("signal is too short for the configured zero-phase filter")
    return signal.sosfiltfilt(sos, values, axis=0).astype(np.float32)
```

P0 的 M0 输入最终为 10 channels：6 个标准化原始 IMU、标准化 `acc_mag/gyro_mag`、以及 broadcast 到时间轴的 `acc_valid/gyro_valid`；mask 不参与标准化。P1 的低通/动态分量只新增通道或配置分支，永远不删除 P0 原始通道。

- [ ] **Step 5: 以 toy 数据验证重采样和真实 sample 的小报告**

Run:

```powershell
python -m pytest tests/test_timebase.py tests/test_preprocess.py -q
python -m eating_detection audit --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" --output-dir "artifacts\audit\sample" --limit-files 2 --max-rows 2000
```

Expected: 目标测试 PASS；报告新增每个流的正时间戳间隔中位数、重复率、timestamp-zero 比例、PPG 全零比例和统一时间轴覆盖范围。输出中明确 `resample_hz=25`，不产生全量 `.npy/.npz`。

- [ ] **Step 6: 提交时间轴/P0 处理**

```powershell
git add src/eating_detection/timebase.py src/eating_detection/preprocess.py src/eating_detection/io.py tests/test_timebase.py tests/test_preprocess.py
git commit -m "feat: restore sensor timebase and preserve quality masks"
```

### Task 4: 餐段标签、participant split 和 manifest

**Files:**

- Create: `src/eating_detection/labels.py`
- Create: `src/eating_detection/splits.py`
- Create: `tests/test_labels.py`
- Create: `tests/test_splits.py`
- Modify: `src/eating_detection/io.py`
- Modify: `src/eating_detection/cli.py`

选择链：比赛是连续事件 IoU，不是窗口 accuracy；窗口边界天然含标注误差 → 以 half-open 时间区间、可配置 overlap 和 soft boundary 派生标签；相邻窗口高度相关且 participant 有个体特征 → 只按 participant 划分，test 只建立 manifest 不进入 train/val。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_labels.py
from eating_detection.labels import clean_interval, label_window


def test_reversed_interval_is_swapped_and_reported():
    interval, reason = clean_interval(20, 10, coverage=(0, 30))
    assert interval == (10, 20)
    assert reason == "reversed_swapped"


def test_equal_interval_is_excluded_from_positive_training():
    interval, reason = clean_interval(10, 10, coverage=(0, 30))
    assert interval is None
    assert reason == "zero_duration_excluded"


def test_window_label_uses_overlap_and_soft_boundary():
    assert label_window((0, 10), [(5, 15)], positive_overlap=0.25, mode="soft") == 0.5
    assert label_window((0, 10), [(20, 30)], positive_overlap=0.25, mode="soft") == 0.0
    assert label_window((0, 10), [(1, 4)], positive_overlap=0.25, mode="ignore") is None
```

```python
# tests/test_splits.py
from eating_detection.splits import make_group_split, assert_disjoint


def test_participants_never_cross_splits():
    split = make_group_split(["p3", "p1", "p2", "p4"], val_fraction=0.25, seed=7)
    assert_disjoint(split)
    assert not (set(split.train) & set(split.val))
    assert set(split.train) | set(split.val) == {"p1", "p2", "p3", "p4"}


def test_same_seed_is_deterministic():
    assert make_group_split(["p1", "p2", "p3"], 0.34, 7) == make_group_split(["p1", "p2", "p3"], 0.34, 7)
```

- [ ] **Step 2: 运行失败测试**

```powershell
python -m pytest tests/test_labels.py tests/test_splits.py -q
```

Expected: FAIL with missing modules/functions。

- [ ] **Step 3: 实现明确的餐段清洗规则和窗口标签**

```python
# src/eating_detection/labels.py
from dataclasses import dataclass


@dataclass(frozen=True)
class MealRecord:
    participant_id: str
    start_ms: int
    end_ms: int
    quality_reason: str


def clean_interval(start_ms: int | None, end_ms: int | None,
                   coverage: tuple[int, int]) -> tuple[tuple[int, int] | None, str]:
    if start_ms is None or end_ms is None:
        return None, "missing_endpoint"
    start, end = int(start_ms), int(end_ms)
    reason = "ok"
    if start > end:
        start, end = end, start
        reason = "reversed_swapped"
    if start == end:
        return None, "zero_duration_excluded"
    start = max(start, coverage[0])
    end = min(end, coverage[1])
    if end <= start:
        return None, "outside_sensor_coverage"
    if reason == "ok" and (start == coverage[0] or end == coverage[1]):
        reason = "clipped_to_coverage"
    return (start, end), reason


def label_window(window: tuple[int, int], intervals: list[tuple[int, int]],
                 positive_overlap: float, mode: str) -> float | None:
    w0, w1 = window
    duration = w1 - w0
    overlap = max((min(w1, e) - max(w0, s) for s, e in intervals), default=0)
    ratio = max(0.0, min(1.0, overlap / duration))
    if ratio == 0:
        return 0.0
    if ratio >= positive_overlap:
        return 1.0
    if mode == "soft":
        return ratio
    if mode == "ignore":
        return None
    raise ValueError("mode must be soft or ignore")
```

规则是：缺端点报告并排除；反序交换并报告；相同端点排除；超出覆盖范围裁剪并报告，裁剪后无正长度则排除。默认 `boundary_mode=soft`，BCE target 保持在 `[0,1]`；`ignore` 模式由 dataset 返回 `loss_mask=False`。

- [ ] **Step 4: 实现 participant split 和 manifest**

```python
# src/eating_detection/splits.py
from dataclasses import dataclass, asdict
import json
import random
from pathlib import Path


@dataclass(frozen=True)
class GroupSplit:
    train: tuple[str, ...]
    val: tuple[str, ...]


def make_group_split(participants: list[str], val_fraction: float, seed: int) -> GroupSplit:
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be between 0 and 1")
    groups = sorted(set(participants))
    if len(groups) < 2:
        raise ValueError("at least two participants are required")
    rng = random.Random(seed)
    rng.shuffle(groups)
    val_count = max(1, round(len(groups) * val_fraction))
    val = tuple(sorted(groups[:val_count]))
    train = tuple(sorted(groups[val_count:]))
    return GroupSplit(train=train, val=val)


def assert_disjoint(split: GroupSplit) -> None:
    if set(split.train) & set(split.val):
        raise AssertionError("participant appears in both train and val")


def save_manifest(path: Path, split: GroupSplit, excluded_test: list[str]) -> None:
    assert_disjoint(split)
    path.write_text(json.dumps({**asdict(split), "excluded_test": sorted(excluded_test)},
                               ensure_ascii=False, indent=2), encoding="utf-8")
```

训练/验证 participant 由训练元数据与传感器目录 canonical ID 的交集产生；test participant 只进入 `excluded_test`。manifest 必须保存 seed、原始 ID→canonical ID 映射、划分和生成配置，训练时加载 manifest 而不是重新随机划分。

- [ ] **Step 5: 运行 toy 和 sample manifest 检查**

```powershell
python -m pytest tests/test_labels.py tests/test_splits.py -q
python -m eating_detection make-manifest --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" --output "artifacts\splits\m0_manifest.json" --seed 7 --val-fraction 0.2
```

Expected: 目标测试 PASS；manifest 有 `train`、`val`、`excluded_test`、`seed` 和 ID alias；命令打印 `SPLIT_PASS train_groups=... val_groups=...`，并在程序内断言 train/val 无交集。

- [ ] **Step 6: 提交标签和 split**

```powershell
git add src/eating_detection/labels.py src/eating_detection/splits.py src/eating_detection/io.py src/eating_detection/cli.py tests/test_labels.py tests/test_splits.py
git commit -m "feat: add interval labels and participant-grouped splits"
```

### Task 5: 窗口数据集、事件解码和竞赛指标

**Files:**

- Create: `src/eating_detection/dataset.py`
- Create: `src/eating_detection/metrics.py`
- Create: `src/eating_detection/decoding.py`
- Create: `tests/test_dataset.py`
- Create: `tests/test_metrics.py`
- Create: `tests/test_decoding.py`

选择链：模型输出窗口概率，比赛评价连续事件 → Dataset 只提供窗口，独立 decoder 恢复连续区间；所有模型共用 metrics 防止后处理差异掩盖模型差异。IoU 使用 half-open 区间，严格 `IoU > 0.25`；匹配必须一次性且确定性，空预测/空真值返回零 TP/FP/FN 而不抛异常。

- [ ] **Step 1: 先写指标、解码和数据集失败测试**

```python
# tests/test_metrics.py
from eating_detection.metrics import event_metrics, interval_iou


def test_iou_threshold_is_strict():
    assert interval_iou((0, 10), (7, 17)) == 3 / 17
    assert interval_iou((0, 3), (1, 4)) == 0.5
    assert event_metrics([(0, 3)], [(1, 4)], iou_threshold=0.25).tp == 1
    assert interval_iou((0, 3), (2, 4)) == 0.25
    assert event_metrics([(0, 3)], [(2, 4)], iou_threshold=0.25).fp == 1
    assert event_metrics([(0, 10)], [(10, 20)], iou_threshold=0.25).fp == 1


def test_empty_predictions_and_truth_are_safe():
    assert event_metrics([], [], 0.25).as_dict() == {"tp": 0, "fp": 0, "fn": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "start_mae_ms": None, "end_mae_ms": None}
    assert event_metrics([(0, 10)], [], 0.25).fp == 1
    assert event_metrics([], [(0, 10)], 0.25).fn == 1
```

```python
# tests/test_decoding.py
from eating_detection.decoding import decode_windows


def test_decode_merges_adjacent_positive_windows_and_removes_short_segments():
    windows = [(0, 10), (5, 15), (30, 40)]
    events = decode_windows(windows, [0.9, 0.8, 0.7], threshold=0.5, merge_gap_ms=0, min_duration_ms=12)
    assert events == [(0, 15)]
```

```python
# tests/test_dataset.py
import torch

from eating_detection.dataset import WindowRecord, WindowDataset, ParticipantBatchSampler


def test_window_dataset_shape_and_batch_groups():
    records = [WindowRecord("p1", 0, 4, torch.zeros(10, 8), 1.0), WindowRecord("p1", 4, 8, torch.ones(10, 8), 0.0)]
    dataset = WindowDataset(records)
    x, y, participant = dataset[0]
    assert x.shape == (10, 8)
    assert y.item() == 1.0
    assert participant == "p1"
    batches = list(ParticipantBatchSampler(dataset, batch_size=2))
    assert batches == [[0, 1]]
```

- [ ] **Step 2: 运行失败测试**

```powershell
python -m pytest tests/test_metrics.py tests/test_decoding.py tests/test_dataset.py -q
```

Expected: FAIL with missing modules/functions。

- [ ] **Step 3: 实现事件 IoU 和确定性 one-to-one 匹配**

```python
# src/eating_detection/metrics.py
from dataclasses import dataclass
from typing import Sequence


def interval_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


@dataclass(frozen=True)
class EventMetrics:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    start_mae_ms: float | None
    end_mae_ms: float | None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def event_metrics(predicted: Sequence[tuple[int, int]], truth: Sequence[tuple[int, int]],
                  iou_threshold: float) -> EventMetrics:
    candidates = sorted(((interval_iou(p, t), i, j)
                         for i, p in enumerate(predicted)
                         for j, t in enumerate(truth)
                         if interval_iou(p, t) > iou_threshold),
                        key=lambda item: (-item[0], item[1], item[2]))
    used_p, used_t, matches = set(), set(), []
    for score, i, j in candidates:
        if i not in used_p and j not in used_t:
            used_p.add(i); used_t.add(j); matches.append((i, j))
    tp, fp, fn = len(matches), len(predicted) - len(matches), len(truth) - len(matches)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    if matches:
        start = sum(abs(predicted[i][0] - truth[j][0]) for i, j in matches) / len(matches)
        end = sum(abs(predicted[i][1] - truth[j][1]) for i, j in matches) / len(matches)
    else:
        start = end = None
    return EventMetrics(tp, fp, fn, precision, recall, f1, start, end)
```

- [ ] **Step 4: 实现独立 decoder 和验证集参数搜索**

```python
# src/eating_detection/decoding.py
def decode_windows(windows, probabilities, threshold=0.5,
                   merge_gap_ms=0, min_duration_ms=0):
    active = [w for w, p in zip(windows, probabilities) if p >= threshold]
    if not active:
        return []
    events = []
    start, end = active[0]
    for next_start, next_end in active[1:]:
        if next_start - end <= merge_gap_ms:
            end = max(end, next_end)
        else:
            if end - start >= min_duration_ms:
                events.append((start, end))
            start, end = next_start, next_end
    if end - start >= min_duration_ms:
        events.append((start, end))
    return events


def tune_decoder(validation_windows, validation_probabilities, validation_truth,
                 iou_threshold=0.25):
    best = None
    for threshold in (0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80):
        for merge_gap_ms in (0, 3000, 6000, 9000):
            for min_duration_ms in (0, 3000, 6000):
                predicted = [decode_windows(w, p, threshold, merge_gap_ms, min_duration_ms)
                             for w, p in zip(validation_windows, validation_probabilities)]
                score = sum(event_metrics(x, y, iou_threshold).f1 for x, y in zip(predicted, validation_truth))
                candidate = (score, -threshold, -merge_gap_ms, -min_duration_ms,
                             threshold, merge_gap_ms, min_duration_ms)
                if best is None or candidate > best:
                    best = candidate
    assert best is not None
    return {"threshold": best[4], "merge_gap_ms": best[5], "min_duration_ms": best[6]}
```

实际实现中 `tune_decoder` 必须把每个 participant 的 metrics 先求均值再比较，避免窗口/事件多的人支配阈值。test 不传入该函数。

- [ ] **Step 5: 实现窗口 Dataset 和不跨 participant 的 sampler**

```python
# src/eating_detection/dataset.py
from dataclasses import dataclass
import torch
from torch.utils.data import Dataset, Sampler


@dataclass(frozen=True)
class WindowRecord:
    participant: str
    start_ms: int
    end_ms: int
    features: torch.Tensor
    label: float
    loss_mask: bool = True


class WindowDataset(Dataset):
    def __init__(self, records):
        self.records = list(records)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        r = self.records[index]
        return r.features, torch.tensor(r.label, dtype=torch.float32), r.participant


class ParticipantBatchSampler(Sampler[list[int]]):
    def __init__(self, dataset: WindowDataset, batch_size: int):
        self.groups = {}
        for index, record in enumerate(dataset.records):
            self.groups.setdefault(record.participant, []).append(index)
        self.batch_size = batch_size

    def __iter__(self):
        for participant in sorted(self.groups):
            indices = self.groups[participant]
            for start in range(0, len(indices), self.batch_size):
                yield indices[start:start + self.batch_size]

    def __len__(self):
        return sum((len(v) + self.batch_size - 1) // self.batch_size for v in self.groups.values())
```

- [ ] **Step 6: 运行测试并提交事件闭环基础**

```powershell
python -m pytest tests/test_dataset.py tests/test_metrics.py tests/test_decoding.py -q
```

Expected: 所有测试 PASS；空输入、严格阈值和单 participant batch 行为均被覆盖。

```powershell
git add src/eating_detection/dataset.py src/eating_detection/metrics.py src/eating_detection/decoding.py tests/test_dataset.py tests/test_metrics.py tests/test_decoding.py
git commit -m "feat: add window dataset and event-level evaluation"
```

## 3. 阶段二：模型与竞赛实验

### Task 6: 实现 M0 IMU 1D CNN 和加权 BCE 训练循环

**Files:**

- Create: `src/eating_detection/models.py`
- Create: `src/eating_detection/training.py`
- Create: `tests/test_models.py`
- Modify: `tests/test_training.py`
- Modify: `src/eating_detection/dataset.py`
- Modify: `src/eating_detection/cli.py`

选择链：第一目标是稳定闭环、8 GB 显存和便于定位失败 → 小型 3-block Conv1d 足够验证局部动作模式；正窗口通常稀少 → 训练集负/正比例构造 `pos_weight`，不手动 sigmoid；事件 F1/MAE 只在验证集解码后监控。

- [ ] **Step 1: 先写 shape、mask 和 loss 失败测试**

```python
# tests/test_models.py
import torch

from eating_detection.models import IMUCNN


def test_m0_accepts_batch_channel_time_and_returns_logits():
    model = IMUCNN(in_channels=10)
    logits = model(torch.randn(3, 10, 125))
    assert logits.shape == (3,)
    assert torch.isfinite(logits).all()


def test_m0_rejects_wrong_channel_count():
    model = IMUCNN(in_channels=10)
    try:
        model(torch.randn(2, 9, 125))
    except ValueError as exc:
        assert "channels" in str(exc)
    else:
        raise AssertionError("wrong channel count was accepted")
```

```python
# tests/test_training.py additions
from eating_detection.training import compute_pos_weight


def test_pos_weight_uses_only_train_labels():
    assert compute_pos_weight([0.0, 0.0, 1.0, 1.0, 1.0]) == 2 / 3
```

- [ ] **Step 2: 运行目标测试确认模型不存在**

```powershell
python -m pytest tests/test_models.py tests/test_training.py -q
```

Expected: FAIL with missing `IMUCNN`/training symbols。

- [ ] **Step 3: 实现 M0，严格保持 `(B,C,T)` 和 logits**

```python
# src/eating_detection/models.py
import torch
from torch import nn


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size=5, padding=2),
            nn.BatchNorm1d(out_channels),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )

    def forward(self, x):
        return self.net(x)


class IMUCNN(nn.Module):
    def __init__(self, in_channels: int = 10):
        super().__init__()
        self.in_channels = in_channels
        self.encoder = nn.Sequential(
            ConvBlock(in_channels, 32),
            ConvBlock(32, 64),
            ConvBlock(64, 96),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(96, 1)

    def forward(self, x):
        if x.ndim != 3 or x.shape[1] != self.in_channels:
            raise ValueError(f"expected (batch, channels, time) with {self.in_channels} channels")
        return self.head(self.encoder(x).squeeze(-1)).squeeze(-1)
```

- [ ] **Step 4: 实现 seed、pos_weight、训练 batch 和 checkpoint**

```python
# src/eating_detection/training.py
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
    positives = sum(float(y) > 0 for y in labels)
    negatives = sum(float(y) == 0 for y in labels)
    if positives == 0:
        raise ValueError("training split has no positive windows")
    return negatives / positives


def train_one_batch(model, optimizer, x, y, pos_weight: float) -> float:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    logits = model(x)
    loss = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(pos_weight, device=logits.device)
    )(logits, y)
    loss.backward()
    optimizer.step()
    return float(loss.detach().cpu())


def save_checkpoint(path: Path, model, optimizer, config, split_manifest, stats, epoch, metrics):
    payload = {
        "model": model.state_dict(), "optimizer": optimizer.state_dict(),
        "config": config, "split_manifest": split_manifest, "stats": stats,
        "epoch": epoch, "metrics": metrics,
    }
    torch.save(payload, path)
```

loss 接收 logits；只有 `torch.sigmoid(logits)` 进入 decoder。训练 batch 必须由 `ParticipantBatchSampler` 产生，或在 collate 后 assert batch 内 participant 唯一。checkpoint 必须包含配置、participant manifest、标准化均值/标准差、seed、epoch 和验证指标。

- [ ] **Step 5: 实现 `train` sample smoke，不先扫描全量**

CLI 命令：

```powershell
python -m eating_detection train --config "E:\bme_compitition\configs\m0_p0.yaml" --data-root "E:\bme_compitition\official_test_dataset\Data" --limit-files 2 --max-rows 2000 --epochs 1 --batch-size 4 --output-dir "artifacts\smoke\m0"
```

Expected：先打印 `participants train=... val=...`、`features shape=(N,10,T)`、`pos_weight=...`，再完成至少一个 optimizer step，写入 `artifacts\smoke\m0\checkpoint.pt` 和 `window_probabilities.jsonl`，最后打印 `TRAIN_SMOKE_PASS`。如果 sample 没有正餐段，命令应明确报 `training split has no positive windows`，并指导使用包含标签的另一小样本，而不是把所有窗口改成负样本。

- [ ] **Step 6: 运行完整单元测试并提交 M0**

```powershell
python -m pytest -q
```

Expected: 当前全部已实现测试 PASS；测试输出没有读取 `official_test_dataset`。

```powershell
git add src/eating_detection/models.py src/eating_detection/training.py src/eating_detection/dataset.py src/eating_detection/cli.py tests/test_models.py tests/test_training.py
git commit -m "feat: add weighted IMU convolutional baseline"
```

### Task 7: 完成端到端 M0 验收和 README 最小运行路径

**Files:**

- Modify: `README.md`
- Modify: `src/eating_detection/cli.py`
- Modify: `src/eating_detection/training.py`
- Create: `tests/test_cli_smoke.py`
- Create: `artifacts` 下的本地 sample 输出（不提交）

选择链：只有读取→标签→训练→事件输出→IoU/F1/MAE 可重复，后续消融才有解释力 → 固定 M0/P0 配置、保存 split/config/stats/probabilities、从 validation 调阈值，再对 test 保持隔离。

- [ ] **Step 1: 先写 CLI 闭环失败测试**

```python
# tests/test_cli_smoke.py
import json
from eating_detection.cli import run_toy_pipeline


def test_toy_pipeline_writes_event_metrics(tmp_path):
    result = run_toy_pipeline(tmp_path, seed=7)
    assert result["status"] == "PASS"
    report = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert {"precision", "recall", "f1", "start_mae_ms", "end_mae_ms"} <= report
```

- [ ] **Step 2: 运行失败测试**

```powershell
python -m pytest tests/test_cli_smoke.py -q
```

Expected: FAIL，因为 toy pipeline 尚未定义。

- [ ] **Step 3: 实现最小 toy pipeline 和真实 CLI 输出契约**

`run_toy_pipeline` 使用内存中的两个 participant、人工构造窗口概率和区间，调用与真实流程相同的 `decode_windows`、`event_metrics`，写 `metrics.json`；它不能绕过 metrics 实现，也不能写真实数据目录。真实 `train` 命令必须输出：

```text
CONFIG_SAVED artifacts/.../config.yaml
SPLIT_SAVED artifacts/.../split_manifest.json
TRAIN_EPOCH epoch=1 loss=...
VAL_EVENTS f1=... precision=... recall=... start_mae_ms=... end_mae_ms=...
TRAIN_SMOKE_PASS
```

- [ ] **Step 4: 运行 toy + sample M0，固定验证集 decoder 参数**

```powershell
python -m pytest tests/test_cli_smoke.py -q
python -m eating_detection train --config "E:\bme_compitition\configs\m0_p0.yaml" --data-root "E:\bme_compitition\official_test_dataset\Data" --limit-files 2 --max-rows 2000 --epochs 1 --batch-size 4 --output-dir "artifacts\smoke\m0_e2e"
python -m eating_detection evaluate --run-dir "artifacts\smoke\m0_e2e" --split val
```

Expected: toy 测试 PASS；真实 sample 运行生成 `config.yaml`、`split_manifest.json`、`normalization.json`、窗口概率、事件预测和 `metrics.json`。阈值只由 val 调整；命令输出明确 `test_not_used=true`。

- [ ] **Step 5: 写 README 的可复现最小路径**

README 至少包括：

1. 原始数据只读、数据路径通过 `--data-root` 传入、`artifacts/` 不进 Git。
2. `conda activate smartwatch-eating`、`python -m pip install -e ".[dev]"`、GPU 验证命令。
3. sample audit 和 M0 smoke 的完整 PowerShell 命令。
4. 完整运行必须使用 participant manifest，不能随机切相邻窗口。
5. 事件指标定义：严格 IoU `>0.25`、Precision/Recall/F1 和正确匹配的 start/end MAE。
6. `pos_weight` 只来自 train，threshold/hysteresis/merge/min-duration 只来自 val。
7. 当前 M0 输入 10 channels 和 checkpoint 内容。

- [ ] **Step 6: 运行验证并提交可提交基线**

```powershell
python -m pytest -q
git status --short
git diff --check
```

Expected: 测试全 PASS；`git diff --check` 无输出；`git status` 只出现计划内的 tracked 文件，sample output 位于 ignored 目录。

```powershell
git add README.md src/eating_detection/cli.py src/eating_detection/training.py tests/test_cli_smoke.py
git commit -m "docs: document reproducible M0 end-to-end run"
```

## 4. 只有验证支持时才启动的实验

下面任务不能阻塞 Task 1–7。每个实验复制 M0 的 participant manifest、seed 和 decoder 评估协议，每次只改变一个主要因素；若 gate 不满足，保留 M0 并记录“未启动/淘汰”的原因，不为凑结构写无效代码。

### Task 8: 采样率、滤波和方向鲁棒性消融

**Files:**

- Create: `configs/experiments/p0_15hz.yaml`
- Create: `configs/experiments/p0_16hz.yaml`
- Create: `configs/experiments/p0_50hz.yaml`
- Create: `configs/experiments/p1_filter.yaml`
- Create: `configs/experiments/p2_direction.yaml`
- Modify: `src/eating_detection/preprocess.py`
- Modify: `src/eating_detection/training.py`
- Create: `tests/test_ablations.py`

- [ ] **Step 1: 写消融配置和测试**

```yaml
# configs/experiments/p0_15hz.yaml
base_config: configs/m0_p0.yaml
resample_hz: 15
preprocess_variant: p0_raw_mask
reuse_split_manifest: artifacts/splits/m0_manifest.json
```

```yaml
# configs/experiments/p0_16hz.yaml
base_config: configs/m0_p0.yaml
resample_hz: 16
preprocess_variant: p0_raw_mask
reuse_split_manifest: artifacts/splits/m0_manifest.json
```

```yaml
# configs/experiments/p0_50hz.yaml
base_config: configs/m0_p0.yaml
resample_hz: 50
preprocess_variant: p0_raw_mask
reuse_split_manifest: artifacts/splits/m0_manifest.json
```

```yaml
# configs/experiments/p1_filter.yaml
base_config: configs/m0_p0.yaml
resample_hz: 25
preprocess_variant: p1_lowpass_dynamic
lowpass_cutoff_hz: 1.0
dynamic_band_hz: [5.0, 10.0]
median_kernel: 5
reuse_split_manifest: artifacts/splits/m0_manifest.json
```

```yaml
# configs/experiments/p2_direction.yaml
base_config: configs/m0_p0.yaml
resample_hz: 25
preprocess_variant: p2_train_axis_augmentation
axis_mirror_probability: 0.5
inference_direction_enumeration: false
wear_feature: false
reuse_split_manifest: artifacts/splits/m0_manifest.json
```

```python
# tests/test_ablations.py
from eating_detection.preprocess import apply_variant


def test_p0_always_keeps_raw_imu_and_masks():
    out = apply_variant("p0_raw_mask", raw_imu_channels=6, magnitude_channels=2, mask_channels=2)
    assert out["channels"] == 10
    assert out["keeps_raw"] is True
```

- [ ] **Step 2: 实现可回退的变体选择器**

```python
# src/eating_detection/preprocess.py addition
def apply_variant(name: str, raw_imu_channels: int, magnitude_channels: int,
                  mask_channels: int) -> dict[str, object]:
    if name == "p0_raw_mask":
        return {"channels": raw_imu_channels + magnitude_channels + mask_channels,
                "keeps_raw": True, "derived": []}
    if name == "p1_lowpass_dynamic":
        return {"channels": raw_imu_channels + magnitude_channels + mask_channels + 6,
                "keeps_raw": True, "derived": ["lowpass", "dynamic", "median"]}
    if name == "p2_train_axis_augmentation":
        return {"channels": raw_imu_channels + magnitude_channels + mask_channels,
                "keeps_raw": True, "derived": ["train_axis_mirror"]}
    raise ValueError(f"unknown preprocess variant: {name}")
```

- [ ] **Step 3: 在同一 participant split 上运行 15/16/25/50 Hz**

```powershell
python -m pytest tests/test_ablations.py -q
python -m eating_detection train --config configs/m0_p0.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\p0_25hz --epochs 3
python -m eating_detection train --config configs/experiments/p0_15hz.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\p0_15hz --epochs 3
python -m eating_detection train --config configs/experiments/p0_16hz.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\p0_16hz --epochs 3
python -m eating_detection train --config configs/experiments/p0_50hz.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\p0_50hz --epochs 3
```

Expected: 每个 run 保存配置、participant 级 F1 均值/标准差/最差个体、边界 MAE、窗口数、实际长度和训练时间。选择逻辑是先看事件 F1，再在差异 `<0.01` 时选 participant 波动更小、MAE 更好、频率更低者；短动作漏检时才保留 25/50 Hz。

- [ ] **Step 4: 运行 P1/P2 单因素消融**

P1 只增加中值/低通/动态分量派生通道；P2 只增加合法轴镜像或有限方向增强；不使用 test 的 `dietaryHand`，仅在训练时使用可信 `wear`（若测试协议明确提供）。每个 run 共享 M0 split、epoch 上限和 decoder tuning。

```powershell
python -m eating_detection train --config configs/experiments/p1_filter.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\p1_filter --epochs 3
python -m eating_detection train --config configs/experiments/p2_direction.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\p2_direction --epochs 3
```

Expected: 只有事件 F1 提升、start/end MAE 不恶化且 participant 间不更不稳定的变体进入下一实验；否则配置和报告保留为淘汰证据。

- [ ] **Step 5: 运行测试并提交实验配置**

```powershell
python -m pytest -q
git add configs/experiments src/eating_detection/preprocess.py src/eating_detection/training.py tests/test_ablations.py
git commit -m "exp: compare sampling and robustness ablations"
```

### Task 9: M1 独立 PPG encoder、特征级融合和 modality dropout

**Files:**

- Modify: `src/eating_detection/models.py`
- Modify: `src/eating_detection/dataset.py`
- Modify: `src/eating_detection/training.py`
- Modify: `src/eating_detection/cli.py`
- Create: `tests/test_m1_fusion.py`
- Create: `configs/m1_imu_ppg.yaml`

启动 gate：M0/P0 已有稳定 sample/full-data 闭环，且 PPG audit 已报告有效比例；如果 PPG 大部分无效，先做 IMU-only 结果，不把缺失模态当作零信号的真实观测。

- [ ] **Step 1: 先写 M1 shape 和 modality dropout 失败测试**

```python
# tests/test_m1_fusion.py
import torch
from eating_detection.models import IMUPPGFusion


def test_m1_accepts_independent_modalities_and_quality_mask():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45)
    logits = model(torch.randn(2, 10, 125), torch.randn(2, 45, 125), torch.tensor([[1., 0.], [0., 1.]]))
    assert logits.shape == (2,)


def test_m1_can_drop_ppg_without_nan():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45)
    logits = model(torch.randn(2, 10, 125), torch.zeros(2, 45, 125), torch.zeros(2, 2))
    assert torch.isfinite(logits).all()
```

- [ ] **Step 2: 实现独立 encoder 和普通 feature concat 优先路径**

PPG encoder 输入为 44 个标准化 PPG 通道 + 1 个 PPG quality mask；IMU encoder 与 M0 相同。中间 embedding 拼接后接 gate/head，`modality_mask` 作为额外 2 维特征。训练时随机将 IMU 或 PPG mask 置 0，并将对应值置 0；评估分别比较 IMU-only、PPG-only、data-level concat、feature-level concat 和 feature-level gate。

```python
# src/eating_detection/models.py addition
class TemporalEncoder(nn.Module):
    def __init__(self, in_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(in_channels, 32, 5, padding=2), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 64, 5, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


class IMUPPGFusion(nn.Module):
    def __init__(self, imu_channels: int = 10, ppg_channels: int = 45):
        super().__init__()
        self.imu_encoder = TemporalEncoder(imu_channels)
        self.ppg_encoder = TemporalEncoder(ppg_channels)
        self.gate = nn.Sequential(nn.Linear(128 + 2, 64), nn.ReLU(), nn.Linear(64, 2), nn.Sigmoid())
        self.head = nn.Linear(128, 1)

    def forward(self, imu, ppg, modality_mask):
        imu_embedding = self.imu_encoder(imu)
        ppg_embedding = self.ppg_encoder(ppg)
        fused = torch.cat([imu_embedding, ppg_embedding], dim=1)
        gate = self.gate(torch.cat([fused, modality_mask], dim=1))
        fused = torch.cat([imu_embedding * gate[:, :1], ppg_embedding * gate[:, 1:]], dim=1)
        return self.head(fused).squeeze(-1)
```

```yaml
# configs/m1_imu_ppg.yaml
base_config: configs/m0_p0.yaml
model: imu_ppg_feature_fusion
ppg_channels: 45
modality_dropout: 0.25
reuse_split_manifest: artifacts/splits/m0_manifest.json
```

- [ ] **Step 3: 运行同一 split 的五组对照**

```powershell
python -m pytest tests/test_m1_fusion.py -q
python -m eating_detection train --config configs/m1_imu_ppg.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\m1_feature --epochs 3
python -m eating_detection evaluate --run-dir artifacts\experiments\m1_feature --split val --mask-scenarios imu_only,ppg_only,both
```

Expected: 记录各模态的有效比例、遮挡后的性能下降、event F1、participant 标准差、边界 MAE 和推理时间。只有特征级融合在主验证集有稳定收益且缺失模态退化可控时保留；门控若不稳定就退回普通 concat。

- [ ] **Step 4: 测试并提交 M1**

```powershell
python -m pytest -q
git add configs/m1_imu_ppg.yaml src/eating_detection/models.py src/eating_detection/dataset.py src/eating_detection/training.py src/eating_detection/cli.py tests/test_m1_fusion.py
git commit -m "feat: add optional robust IMU PPG fusion"
```

### Task 10: 按错误类型选择 M2、M3 或 M4，最多启动一个高级方向

**Files:**

- Create: `src/eating_detection/context_model.py`（仅 M1 瞬时误报 gate 通过时）
- Create: `src/eating_detection/tcn.py`（仅局部连续性/边界 gate 通过时）
- Create: `src/eating_detection/self_supervised.py`（仅 M0/M1 稳定且时间允许时）
- Create: `tests/test_advanced_models.py`
- Create: `configs/experiments/m2_context.yaml`
- Create: `configs/experiments/m3_tcn.yaml`
- Create: `configs/experiments/m4_ssl.yaml`
- Modify: `README.md`

启动决策必须来自 `artifacts/experiments/m1*/error_analysis.json`：

- 若主要错误是短暂 FP，且 M1 已检出大部分正事件 → 只启动 M2；输入是 M1 窗口概率、有效性和间隔，不输入全天原始数组。
- 若主要错误是局部不连续或边界抖动 → 只启动 M3 轻量 TCN/MS-TCN；dilation 扩大局部感受野。
- 若前两者都不是主问题，且未标注数据量足以支撑 → 只启动一次内部 masked reconstruction/contrastive M4。
- 若 gate 不满足 → 不创建对应模型文件，README 记录未启动理由，保留 M0/M1。

- [ ] **Step 1: 写统一高级模型 shape 失败测试**

```python
# tests/test_advanced_models.py
import importlib.util

import pytest
import torch


def test_selected_advanced_model_preserves_batch_length():
    if importlib.util.find_spec("eating_detection.context_model"):
        from eating_detection.context_model import ProbabilityContextModel
        assert ProbabilityContextModel(3)(torch.randn(2, 16, 3)).shape == (2, 16)
    elif importlib.util.find_spec("eating_detection.tcn"):
        from eating_detection.tcn import TinyTCN
        assert TinyTCN(10)(torch.randn(2, 10, 64)).shape == (2, 64)
    else:
        pytest.skip("no evidence-gated advanced model selected")
```

- [ ] **Step 2: 只实现被 gate 选中的一个模型，并先跑失败测试**

若 gate 选 M2，创建 `context_model.py` 并实现 `ProbabilityContextModel(3)`，其 `forward` 输入 `(B,L,3)`、输出 `(B,L)`；最小模型是 `Linear(3,16) -> ReLU -> Conv1d(16,16,3,padding=1) -> ReLU -> Linear(16,1)`，在前向时转置为 Conv1d 的 `(B,C,L)`。若 gate 选 M3，创建 `tcn.py` 并实现 `TinyTCN(10)`，输入 `(B,C,T)`、输出 `(B,T)`，使用两个 dilation 为 1/2 的 padded Conv1d block。两者都不改变事件 decoder。若 gate 选 M4，创建 `self_supervised.py` 的 masked reconstruction encoder，预训练和微调均保存 seed/config，并把预训练数据限制为 train participant。

- [ ] **Step 3: 在同一 val 上比较并执行淘汰规则**

```powershell
python -m pytest tests/test_advanced_models.py -q
python -m eating_detection train --config configs/experiments/m2_context.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest artifacts\splits\m0_manifest.json --output-dir artifacts\experiments\m2_context --epochs 3
```

Expected: 只在对应 gate 的模型命令中运行；如果 event F1 未提升、短零食 Recall 下降、边界 MAE 恶化或 participant 标准差增加，标记淘汰并回到 M1/M0。最终最多选一个高级方向，不能同时堆叠 M2+M3+M4。

- [ ] **Step 4: 测试、更新 README、提交高级实验结论**

```powershell
python -m pytest -q
git add configs/experiments src/eating_detection tests/test_advanced_models.py README.md
git commit -m "exp: evaluate one evidence-gated temporal improvement"
```

## 5. 最终验证、复现和交付

### Task 11: 全量流式运行、可复现检查和最终 README

**Files:**

- Modify: `README.md`
- Modify: `.gitignore`（仅在验证发现新生成物未被忽略时）
- Modify: `src/eating_detection/cli.py`
- Modify: `src/eating_detection/training.py`
- Create: `tests/test_reproducibility.py`

- [ ] **Step 1: 写复现测试**

```python
# tests/test_reproducibility.py
from eating_detection.training import set_seed
import torch


def test_seed_repeats_torch_sequence():
    set_seed(7)
    a = torch.randn(8)
    set_seed(7)
    b = torch.randn(8)
    assert torch.equal(a, b)
```

- [ ] **Step 2: 运行全测试和静态检查**

```powershell
python -m pytest -q
python -m compileall src scripts
git diff --check
```

Expected: pytest 全部 PASS；compileall 无 traceback；diff check 无输出。

- [ ] **Step 3: 用 sample 重新运行并比较 manifest/config/hash**

```powershell
python -m eating_detection audit --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" --output-dir "artifacts\final_check\audit" --limit-files 2 --max-rows 2000
python -m eating_detection train --config configs/m0_p0.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --limit-files 2 --max-rows 2000 --epochs 1 --output-dir "artifacts\final_check\m0"
python -m eating_detection train --config configs/m0_p0.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --limit-files 2 --max-rows 2000 --epochs 1 --output-dir "artifacts\final_check\m0_repeat"
```

Expected: 两次的 seed、split manifest、config 和窗口输出摘要一致；若 GPU 非确定性使浮点 loss 有微小差异，README 说明设备/确定性开关，并要求事件指标在记录精度内一致。sample 运行仍只读取 limit-files/max-rows，不扫描 93 GB。

- [ ] **Step 4: 再运行完整训练和验证；test 只在最终冻结后做一次推理**

```powershell
python -m eating_detection make-manifest --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" --output "artifacts\final\split_manifest.json" --seed 7 --val-fraction 0.2
python -m eating_detection train --config configs/m0_p0.yaml --data-root "E:\bme_compitition\official_test_dataset\Data" --split-manifest "artifacts\final\split_manifest.json" --output-dir "artifacts\final\m0" --epochs 20
python -m eating_detection evaluate --run-dir "artifacts\final\m0" --split val
```

Expected：训练通过所有 participant 流式处理；`metrics.json` 有总计和 participant 级 Precision/Recall/F1/start/end MAE；最佳 threshold 和后处理参数来自 val。未得到用户明确允许前，不运行提交操作；如竞赛要求 test 推理，先冻结 checkpoint/config/decoder，再只运行 test inference，不回头调参。

- [ ] **Step 5: 验证 Git 状态和数据保护**

```powershell
git status --short
git ls-files "official_test_dataset/Data/01_dataset" "official_test_dataset/Data/02_traindataset"
git check-ignore -v artifacts cache checkpoints outputs
```

Expected：`git ls-files` 对原始数据无输出；生成目录被 `.gitignore` 命中；工作区只包含计划内 README/代码/配置/测试/文档。不要使用 `git reset --hard`、删除原始数据或把大数据 add 到 Git。

- [ ] **Step 6: 最终原子提交并按 verification-before-completion 复核**

```powershell
git add README.md .gitignore src tests configs
git commit -m "chore: finalize reproducible eating detection baseline"
git status --short --branch
git log --oneline -6
```

Expected：最终分支干净；README 的命令从当前仓库可执行；最后报告实际 HEAD、环境锁文件、M0/M1 选择、验证集指标和所有未采用方案的证据链。

## 6. 阶段验收与决策记录格式

每个阶段结束时在对应 `artifacts/.../summary.json` 保存如下字段，确保“事实→风险→候选→标准→选择→实验”可回溯：

```json
{
  "facts": ["..."],
  "risk": ["..."],
  "candidates": ["..."],
  "criterion": {"primary": "event_f1", "secondary": ["participant_std", "start_end_mae_ms", "complexity"]},
  "choice": "...",
  "experiment": {"seed": 7, "split_manifest": "...", "config": "..."},
  "metrics": {"event_f1": 0.0, "precision": 0.0, "recall": 0.0, "start_mae_ms": null, "end_mae_ms": null}
}
```

固定淘汰规则：数据闭环失败时不调模型；participant 有交叉时结果无效；test 参与阈值/模型选择时结果无效；滤波/方向/PPG/高级模型没有稳定事件 F1 收益或恶化边界 MAE 时回退；F1 差异小于 0.01 时依次看 participant 标准差、边界 MAE、模型/依赖复杂度。

## 7. 写计划后的自审结果

- **Spec coverage:** 计划覆盖独立 Conda/GPU smoke、流式 93 GB 数据保护、时间戳 0/重复包/全零 PPG mask、统一时间轴后重采样、15/16/25/50 Hz、15 秒/3 秒窗口、P0/P1/P2、participant split、M0/M1/M2/M3/M4 gate、`pos_weight`、事件 IoU/F1/MAE、空输入、README、原子提交和最终复现检查。
- **Placeholder scan:** 本计划没有使用未定义的占位任务或泛化的“稍后实现”步骤；每个代码任务给出接口、实现片段、测试命令和预期结果。条件实验以明确 gate 和淘汰规则表达，不以未定义工作占位。
- **Type consistency:** `WindowRecord.features` 使用 `(C,T)`；`IMUCNN` 接收 `(B,C,T)` 并返回 `(B,)` logits；`BCEWithLogitsLoss` 接收同 shape logits/float targets；`decode_windows` 接收 window/probability 序列并返回区间；`event_metrics` 接收区间并返回 `EventMetrics`；M1 的 modality mask 统一为 `(B,2)`。
- **安全性:** 计划没有任何删除/覆盖原始数据的命令；所有真实路径通过 CLI；数据和生成物保持 Git 忽略；高级模型不能绕过已经验收的 M0/M1 闭环。

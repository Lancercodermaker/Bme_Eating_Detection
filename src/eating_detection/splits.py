from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random


@dataclass(frozen=True)
class GroupSplit:
    train: tuple[str, ...]
    val: tuple[str, ...]


def make_group_split(
    participants: list[str], val_fraction: float, seed: int
) -> GroupSplit:
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be between 0 and 1")
    groups = sorted(set(participants))
    if len(groups) < 2:
        raise ValueError("at least two participants are required")
    rng = random.Random(seed)
    rng.shuffle(groups)
    val_count = min(max(1, round(len(groups) * val_fraction)), len(groups) - 1)
    val = tuple(sorted(groups[:val_count]))
    train = tuple(sorted(groups[val_count:]))
    return GroupSplit(train=train, val=val)


def assert_disjoint(split: GroupSplit) -> None:
    if not split.train or not split.val:
        raise AssertionError("train and val must both contain participants")
    if set(split.train) & set(split.val):
        raise AssertionError("participant appears in both train and val")


def save_manifest(
    path: Path,
    split: GroupSplit,
    excluded_test: list[str],
    seed: int | None = None,
    aliases: dict[str, str] | None = None,
    config: dict[str, object] | None = None,
    unmatched_sensor: list[str] | None = None,
) -> None:
    assert_disjoint(split)
    payload: dict[str, object] = {
        **asdict(split),
        "excluded_test": sorted(excluded_test),
        "id_aliases": aliases or {},
    }
    if seed is not None:
        payload["seed"] = seed
    if config is not None:
        payload["config"] = config
    if unmatched_sensor is not None:
        payload["unmatched_sensor"] = sorted(unmatched_sensor)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    split = GroupSplit(tuple(payload["train"]), tuple(payload["val"]))
    assert_disjoint(split)
    return payload


def make_manifest_from_directories(
    index_dir: Path,
    train_dir: Path,
    output: Path,
    seed: int,
    val_fraction: float,
) -> GroupSplit:
    from .io import discover_participant_aliases, read_meal_participant_aliases

    sensor_aliases = discover_participant_aliases(train_dir)
    meal_aliases = read_meal_participant_aliases(index_dir)
    sensor_ids = set(sensor_aliases.values())
    meal_ids = set(meal_aliases.values())
    reserved_test = {"test"}
    participants = sorted((sensor_ids & meal_ids) - reserved_test)
    if len(participants) < 2:
        raise ValueError("at least two participants need both sensor data and meal metadata")
    split = make_group_split(participants, val_fraction, seed)
    excluded_test = sorted(
        (meal_ids - sensor_ids) | (reserved_test & (sensor_ids | meal_ids))
    )
    aliases = {**sensor_aliases, **meal_aliases}
    unmatched_sensor = sorted(sensor_ids - meal_ids)
    save_manifest(
        output,
        split,
        excluded_test=excluded_test,
        seed=seed,
        aliases=aliases,
        config={
            "index_dir": str(Path(index_dir)),
            "train_dir": str(Path(train_dir)),
            "val_fraction": val_fraction,
        },
        unmatched_sensor=unmatched_sensor,
    )
    return split

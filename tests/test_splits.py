import json

from eating_detection.cli import main
from eating_detection.splits import assert_disjoint, make_group_split, save_manifest


def test_participants_never_cross_splits():
    split = make_group_split(["p3", "p1", "p2", "p4"], val_fraction=0.25, seed=7)
    assert_disjoint(split)
    assert not (set(split.train) & set(split.val))
    assert set(split.train) | set(split.val) == {"p1", "p2", "p3", "p4"}


def test_same_seed_is_deterministic():
    assert make_group_split(["p1", "p2", "p3"], 0.34, 7) == make_group_split(
        ["p1", "p2", "p3"], 0.34, 7
    )


def test_manifest_records_seed_and_raw_id_aliases(tmp_path):
    path = tmp_path / "manifest.json"
    save_manifest(
        path,
        make_group_split(["p1", "p2"], 0.5, 7),
        excluded_test=["test"],
        seed=7,
        aliases={" P1 ": "p1"},
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["seed"] == 7
    assert payload["id_aliases"] == {" P1 ": "p1"}
    assert payload["excluded_test"] == ["test"]


def test_make_manifest_cli_intersects_meal_and_sensor_participants(tmp_path):
    index_dir = tmp_path / "index"
    organized = tmp_path / "train" / "organized"
    index_dir.mkdir()
    (organized / "HNU 1").mkdir(parents=True)
    (organized / "HNU2").mkdir()
    meal_csv = index_dir / "sample_mealinfo.csv"
    meal_csv.write_text(
        "externalid,beforeTime,afterTime\n"
        "HNU1,1000,2000\n"
        "hnu 2,3000,4000\n"
        "test,5000,6000\n",
        encoding="utf-8",
    )
    output = tmp_path / "manifest.json"
    assert (
        main(
            [
                "make-manifest",
                "--index-dir",
                str(index_dir),
                "--train-dir",
                str(tmp_path / "train"),
                "--output",
                str(output),
                "--seed",
                "7",
                "--val-fraction",
                "0.5",
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert set(payload["train"]) | set(payload["val"]) == {"hnu1", "hnu2"}
    assert payload["excluded_test"] == ["test"]


def test_manifest_excludes_reserved_test_participant_even_with_sensor_data(tmp_path):
    index_dir = tmp_path / "index"
    organized = tmp_path / "train" / "organized"
    index_dir.mkdir()
    for participant in ("p1", "p2", "test"):
        (organized / participant).mkdir(parents=True)
    (index_dir / "sample_mealinfo.csv").write_text(
        "externalid,beforeTime,afterTime\n"
        "p1,1000,2000\n"
        "p2,3000,4000\n"
        "test,5000,6000\n",
        encoding="utf-8",
    )
    output = tmp_path / "manifest.json"
    main(
        [
            "make-manifest",
            "--index-dir",
            str(index_dir),
            "--train-dir",
            str(tmp_path / "train"),
            "--output",
            str(output),
            "--seed",
            "7",
            "--val-fraction",
            "0.5",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "test" not in payload["train"]
    assert "test" not in payload["val"]
    assert "test" in payload["excluded_test"]

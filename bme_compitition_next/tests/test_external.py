import pickle

import numpy as np

from eating_event.external import ExternalSequence, iter_fd_sequences, windowize_external_sequence


def test_iter_fd_sequences_preserves_two_wrist_subject_contract(tmp_path) -> None:
    dataset_root = tmp_path / "FD-I"
    dataset_root.mkdir()
    values_left = [np.zeros((16, 6), dtype=np.float64), np.ones((16, 6), dtype=np.float64)]
    values_right = [np.full((16, 6), 2.0), np.full((16, 6), 3.0)]
    labels_left = [np.zeros(16, dtype=np.int32), np.ones(16, dtype=np.int32)]
    labels_right = [np.full(16, 2, dtype=np.int32), np.zeros(16, dtype=np.int32)]
    for name, payload in {
        "X_L.pkl": values_left,
        "X_R.pkl": values_right,
        "Y_L.pkl": labels_left,
        "Y_R.pkl": labels_right,
    }.items():
        with (dataset_root / name).open("wb") as handle:
            pickle.dump(payload, handle)

    sequences = list(iter_fd_sequences(tmp_path, dataset="FD-I"))

    assert len(sequences) == 4
    assert all(isinstance(sequence, ExternalSequence) for sequence in sequences)
    assert {sequence.wrist for sequence in sequences} == {"left", "right"}
    assert sequences[0].values.shape == (16, 6)
    assert set(np.unique(np.concatenate([sequence.labels for sequence in sequences]))) == {0, 1, 2}


def test_windowize_external_sequence_maps_point_labels_to_binary_window_labels() -> None:
    values = np.arange(2048 * 6, dtype=np.float64).reshape(2048, 6)
    labels = np.zeros(2048, dtype=np.int8)
    labels[1000] = 1
    sequence = ExternalSequence("FD-I", "FD-I-000", "left", values, labels, 64.0)

    features, window_labels = windowize_external_sequence(sequence, window_seconds=15.0, step_seconds=7.5)

    assert features.shape[0] == window_labels.shape[0]
    assert features.shape[1] == 111
    assert window_labels.tolist() == [0, 1, 1]

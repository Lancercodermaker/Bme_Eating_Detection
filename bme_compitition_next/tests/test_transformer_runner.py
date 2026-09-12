from scripts.run_transformer_candidate import _chunk_slices


def test_chunk_slices_cover_short_and_long_sequences_without_gaps() -> None:
    assert _chunk_slices(5, sequence_length=8, stride=4) == ((0, 5),)
    assert _chunk_slices(10, sequence_length=4, stride=3) == ((0, 4), (3, 7), (6, 10))


def test_chunk_slices_reject_invalid_arguments() -> None:
    for values in ((0, 4, 2), (4, 0, 2), (4, 2, 0)):
        try:
            _chunk_slices(*values)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid chunk arguments must raise ValueError")

import torch

from eating_detection.training import set_seed


def test_seed_repeats_torch_sequence():
    set_seed(7)
    first = torch.randn(8)
    set_seed(7)
    second = torch.randn(8)
    assert torch.equal(first, second)


def test_set_seed_enables_deterministic_algorithms():
    set_seed(7)
    assert torch.are_deterministic_algorithms_enabled()

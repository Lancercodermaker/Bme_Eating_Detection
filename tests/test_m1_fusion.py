import pytest
import torch

from eating_detection.models import (
    IMUCNN,
    IMUPPGFusion,
    load_compatible_imu_encoder_from_m0,
)
from eating_detection.training import train_m1_one_batch


def _inputs(batch_size: int = 3, time_steps: int = 125):
    return (
        torch.randn(batch_size, 10, time_steps),
        torch.randn(batch_size, 45, time_steps),
        torch.ones(batch_size, 2),
    )


def test_m1_fuses_independent_imu_and_ppg_encoders_with_explicit_masks():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45)
    imu, ppg, modality_mask = _inputs()

    logits = model(imu, ppg, modality_mask)

    assert logits.shape == (3,)
    assert torch.isfinite(logits).all()
    assert model.imu_encoder.in_channels == 10
    assert model.ppg_encoder.in_channels == 45


def test_invalid_ppg_mask_prevents_zero_values_from_being_interpreted_as_observed():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45).eval()
    imu, ppg, _ = _inputs(batch_size=2)
    unavailable_ppg = torch.tensor([[1.0, 0.0], [1.0, 0.0]])

    with torch.inference_mode():
        from_nonzero = model(imu, ppg, unavailable_ppg)
        from_zero = model(imu, torch.zeros_like(ppg), unavailable_ppg)

    torch.testing.assert_close(from_nonzero, from_zero)


def test_m1_handles_missing_modalities_and_rejects_invalid_mask_shape():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45)
    imu, ppg, _ = _inputs(batch_size=2)

    logits = model(imu, torch.zeros_like(ppg), torch.tensor([[1.0, 0.0], [0.0, 1.0]]))

    assert torch.isfinite(logits).all()
    with pytest.raises(ValueError, match="modality_mask"):
        model(imu, ppg, torch.ones(2, 1))


def test_modality_dropout_only_applies_during_training_and_keeps_one_available_branch():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45, modality_dropout=1.0)
    imu, ppg, modality_mask = _inputs(batch_size=4)

    model.train()
    dropped_imu, dropped_ppg, dropped_mask = model.apply_modality_dropout(imu, ppg, modality_mask)
    assert torch.equal(dropped_mask.sum(dim=1), torch.ones(4))
    assert torch.all((dropped_imu == 0).all(dim=(1, 2)) | (dropped_ppg == 0).all(dim=(1, 2)))

    model.eval()
    kept_imu, kept_ppg, kept_mask = model.apply_modality_dropout(imu, ppg, modality_mask)
    torch.testing.assert_close(kept_imu, imu)
    torch.testing.assert_close(kept_ppg, ppg)
    torch.testing.assert_close(kept_mask, modality_mask)


def test_m1_eval_mode_is_deterministic_with_modality_dropout_configured():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45, modality_dropout=1.0).eval()
    imu, ppg, modality_mask = _inputs(batch_size=2)

    with torch.inference_mode():
        first = model(imu, ppg, modality_mask)
        second = model(imu, ppg, modality_mask)

    torch.testing.assert_close(first, second)


def test_incompatible_m0_state_dict_is_refused_without_silent_transfer():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45)

    with pytest.raises(ValueError, match="structurally compatible"):
        load_compatible_imu_encoder_from_m0(model, IMUCNN(in_channels=10).state_dict())


def test_m1_batch_uses_logits_bce_and_updates_parameters():
    torch.manual_seed(7)
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45, modality_dropout=0.0)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    before = [parameter.detach().clone() for parameter in model.parameters()]
    imu, ppg, modality_mask = _inputs(batch_size=4)

    loss = train_m1_one_batch(
        model, optimizer, imu, ppg, modality_mask,
        torch.tensor([0.0, 1.0, 0.0, 1.0]), pos_weight=1.0,
    )

    assert loss >= 0.0
    assert any(not torch.equal(old, new.detach()) for old, new in zip(before, model.parameters()))


def test_m1_cuda_forward_backward_sample():
    if not torch.cuda.is_available():
        pytest.skip("CUDA is not available")
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45, modality_dropout=0.0).cuda()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    imu, ppg, modality_mask = (tensor.cuda() for tensor in _inputs(batch_size=2))

    loss = train_m1_one_batch(
        model, optimizer, imu, ppg, modality_mask,
        torch.tensor([0.0, 1.0], device="cuda"), pos_weight=1.0,
    )

    assert loss >= 0.0

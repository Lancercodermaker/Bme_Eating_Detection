import pytest
import torch

from eating_detection.models import (
    IMUCNN,
    IMUPPGFusion,
    load_compatible_imu_encoder_from_m0,
)
from eating_detection.training import (
    compute_m1_negative_run_weights,
    compute_m1_temporal_run_mask,
    compute_m1_stratum_pos_weights,
    m1_bce_loss,
    m1_stratum_pos_weight_tensor,
    resolve_m1_pos_weight,
    train_m1_one_batch,
)


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


def test_m1_avg4_pooling_preserves_four_temporal_bins_per_modality():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45, pooling="avg4")
    imu, ppg, modality_mask = _inputs(time_steps=125)

    logits = model(imu, ppg, modality_mask)

    assert logits.shape == (3,)
    assert model.imu_encoder.projection.in_features == 96 * 4
    assert model.ppg_encoder.projection.in_features == 96 * 4


def test_m1_avgmax_pooling_preserves_temporal_peak_features_per_modality():
    model = IMUPPGFusion(imu_channels=10, ppg_channels=45, pooling="avgmax")
    imu, ppg, modality_mask = _inputs(time_steps=125)

    logits = model(imu, ppg, modality_mask)

    assert logits.shape == (3,)
    assert model.imu_encoder.projection.in_features == 96 * 2
    assert model.ppg_encoder.projection.in_features == 96 * 2


def test_m1_shared_mean_fusion_uses_one_embedding_head_without_mask_features():
    model = IMUPPGFusion(
        imu_channels=10, ppg_channels=45, fusion_mode="shared_mean"
    )

    assert model.head.in_features == 64
    assert not hasattr(model, "gate")


def test_m1_normalized_mean_fusion_uses_one_embedding_head_without_mask_features():
    model = IMUPPGFusion(
        imu_channels=10, ppg_channels=45, fusion_mode="normalized_mean"
    )

    assert model.head.in_features == 64
    assert not hasattr(model, "gate")


def test_m1_logit_mean_fusion_uses_only_available_modality_logits():
    model = IMUPPGFusion(
        imu_channels=10, ppg_channels=45, fusion_mode="logit_mean"
    ).eval()
    imu, ppg, _ = _inputs(batch_size=2)
    imu_only = torch.tensor([[1.0, 0.0], [1.0, 0.0]])

    assert model.imu_head.in_features == 64
    assert model.ppg_head.in_features == 64
    assert model.missing_logit.shape == (1,)

    with torch.inference_mode():
        from_ppg = model(imu, ppg, imu_only)
        from_zero = model(imu, torch.zeros_like(ppg), imu_only)

    torch.testing.assert_close(from_ppg, from_zero)


def test_m1_logit_min_fusion_is_conservative_when_both_modalities_are_available():
    model = IMUPPGFusion(
        imu_channels=10, ppg_channels=45, fusion_mode="logit_min"
    ).eval()
    with torch.no_grad():
        model.imu_head.weight.zero_()
        model.imu_head.bias.fill_(2.0)
        model.ppg_head.weight.zero_()
        model.ppg_head.bias.fill_(-1.0)
        model.missing_logit.fill_(0.5)
    imu, ppg, _ = _inputs(batch_size=4, time_steps=8)
    modality_mask = torch.tensor(
        [[1.0, 1.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
    )

    with torch.inference_mode():
        logits = model(imu, ppg, modality_mask)

    torch.testing.assert_close(logits, torch.tensor([-1.0, 2.0, -1.0, 0.5]))


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


def test_m1_stratum_weights_use_train_labels_without_availability_shortcut():
    labels = torch.tensor([0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0])
    modality_mask = torch.tensor([
        [1.0, 1.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [1.0, 1.0],
        [1.0, 0.0],
        [1.0, 0.0],
        [0.0, 0.0],
    ])

    weights = compute_m1_stratum_pos_weights(labels, modality_mask)

    assert weights == {"both": 3.0, "imu_only": 1.0, "ppg_only": 0.0, "neither": 0.0}
    batch_weights = m1_stratum_pos_weight_tensor(modality_mask, weights)
    torch.testing.assert_close(batch_weights, torch.tensor([3.0, 3.0, 3.0, 3.0, 1.0, 1.0, 0.0]))

    rare_labels = torch.tensor([1.0] + [0.0] * 10)
    rare_mask = torch.zeros((11, 2))
    capped = compute_m1_stratum_pos_weights(
        rare_labels, rare_mask, max_pos_weight=5.0
    )
    assert capped["neither"] == 5.0


def test_m1_unweighted_bce_removes_global_class_prior_from_training_weight():
    assert resolve_m1_pos_weight("unweighted_bce", 35.17690685668581) == 1.0
    assert resolve_m1_pos_weight("global_bce", 35.17690685668581) == 35.17690685668581


def test_m1_fixed_prior_bce_uses_configured_weight():
    assert (
        resolve_m1_pos_weight(
            "fixed_prior_bce", 35.17690685668581, configured_pos_weight=4.0
        )
        == 4.0
    )


def test_m1_focal_bce_downweights_confident_examples():
    logits = torch.tensor([6.0, -6.0])
    targets = torch.tensor([1.0, 0.0])

    bce = m1_bce_loss(logits, targets, pos_weight=35.1769, loss_mode="global_bce")
    focal = m1_bce_loss(
        logits, targets, pos_weight=35.1769, loss_mode="focal_bce", focal_gamma=2.0
    )

    assert focal < bce


def test_m1_negative_run_weights_only_penalize_long_train_negative_runs():
    labels = torch.tensor([0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    source_ids = ["file-a"] * 6 + ["file-b"] * 3
    starts_ms = [0, 3000, 6000, 9000, 12000, 15000, 0, 3000, 9000]

    weights = compute_m1_negative_run_weights(
        labels,
        source_ids,
        starts_ms,
        step_ms=3000,
        reference_windows=2,
        max_weight=4.0,
    )

    torch.testing.assert_close(
        weights,
        torch.tensor([2.0, 2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
    )


def test_m1_negative_run_bce_uses_sample_weights_without_changing_positive_prior():
    logits = torch.tensor([-2.0, 2.0])
    targets = torch.zeros(2)

    unweighted = m1_bce_loss(
        logits, targets, pos_weight=1.0, loss_mode="negative_run_bce"
    )
    weighted = m1_bce_loss(
        logits,
        targets,
        pos_weight=1.0,
        loss_mode="negative_run_bce",
        sample_weight=torch.tensor([1.0, 4.0]),
    )

    assert weighted > unweighted
    assert resolve_m1_pos_weight("negative_run_bce", 35.17690685668581) == 35.17690685668581


def test_m1_negative_run_weight_cap_is_configurable_for_long_runs():
    labels = torch.zeros(40)
    source_ids = ["file-a"] * 40
    starts_ms = [index * 3000 for index in range(40)]

    capped_four = compute_m1_negative_run_weights(
        labels,
        source_ids,
        starts_ms,
        step_ms=3000,
        reference_windows=8.0,
        max_weight=4.0,
    )
    capped_sixteen = compute_m1_negative_run_weights(
        labels,
        source_ids,
        starts_ms,
        step_ms=3000,
        reference_windows=8.0,
        max_weight=16.0,
    )

    assert torch.all(capped_four == 4.0)
    assert torch.all(capped_sixteen == 5.0)
    assert torch.all(capped_sixteen >= capped_four)


def test_m1_temporal_run_mask_marks_only_contiguous_negative_runs():
    labels = torch.tensor([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0])

    mask = compute_m1_temporal_run_mask(labels, min_run_length=3)

    torch.testing.assert_close(
        mask,
        torch.tensor([True, True, True, False, True, True, True, True, False]),
    )


def test_m1_temporal_run_bce_adds_negative_run_penalty():
    logits = torch.tensor([2.0, 2.0, -2.0, -2.0])
    targets = torch.zeros(4)

    base = m1_bce_loss(logits, targets, pos_weight=1.0, loss_mode="global_bce")
    temporal = m1_bce_loss(
        logits,
        targets,
        pos_weight=1.0,
        loss_mode="temporal_run_bce",
        temporal_run_penalty_weight=2.0,
    )

    assert temporal > base
    assert resolve_m1_pos_weight("temporal_run_bce", 35.17690685668581) == 35.17690685668581


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

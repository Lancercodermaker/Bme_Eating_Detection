# Data Contract Implementation and Validation — 2026-09-17

## Decision state

```text
DATA_CONTRACT = APPROVED
FAILURE_CLASS = DATA_PIPELINE
ARCHITECTURE = FROZEN
FULL_TRAINING = BLOCKED_UNTIL_VALIDATION
```

The approved label contract remains:

```text
window length = 15 s
stride = 7.5 s
POSITIVE iff intersection(window, event) / window_duration >= 0.5
```

The reference paper's 3 s slide is an independent open risk. It was not changed
or mixed into this implementation:

```text
OPEN_RISK: current stride 7.5 s differs from reference-paper 3 s slide.
Owner: future controlled stride experiment.
Status: OPEN; out of scope for this validation.
```

## Event ledger implementation

`participant_eligibility_v3` retains all annotated events and stores orthogonal
fields for `annotation_status`, `sensor_status`, `representability_status`,
`unrepresentable_reason`, `annotation_quality_status`,
`training_eligibility`, `evaluation_eligibility`, and `exclusion_reason`.

Final ledger counts:

| population | count |
|---|---:|
| annotated events | 281 |
| sensor-backed events | 246 |
| representable events | 239 |
| unrepresentable events | 42 |
| label-eligible events | 234 |

Unrepresentable reasons:

| reason | count |
|---|---:|
| `NO_DENSE_WINDOW_SUPPORT` | 7 |
| `METADATA_ONLY_NO_SESSION` | 3 |
| `NO_INDEX_SESSION_OVERLAP` | 12 |
| `OVERLAP_ONLY_INVALID_SENSOR` | 20 |

The 7 no-dense events remain in the annotated ledger. They are not silently
removed from the dataset; they are excluded from label/evaluation populations
with an explicit reason.

## Cache and label regeneration

Old label-bearing caches were not loaded as labels. Their geometry/features were
used only for bounded regeneration because the approved change did not alter
raw parsing, resampling, quality filtering, window length, stride, or feature
semantics. Labels were recomputed from the v3 ledger and written under a new
cache identity.

Final cache:

- 1,127 processed-record caches
- eligibility identity: `event_eligibility_v1`
- stable eligibility ledger hash: `6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d`
- label identity: `window_event_overlap_v1`
- window/stride: 15 s / 7.5 s
- total dense windows: 632,100
- label statistics: POSITIVE 35,948; NEGATIVE 583,145; IGNORE 13,007

`artifacts/g1-formal-cache-v3` is an interrupted intermediate regeneration and
must not be consumed. The authoritative cache for downstream validation is
`artifacts/g1-formal-cache-v3-final`.

## Validation gates

- Pipeline invariant tests: PASS, 96 tests.
- Event representability audit: PASS. Positive candidate events are 234/246
  sensor-backed events (95.12%) and 234/239 representable events (97.91%).
  No `SHORT_DURATION_SUSPECT` event became a positive-label source.
- Small-set overfit: PASS. HNU21022, 10 sessions, 5,788 windows,
  labeled-window accuracy 1.0.
- Formal G1 candidate coverage: FAIL, `DATA/PIPELINE`. This gate also failed
  under the old contract; the rerun is recorded and the result is not hidden.
- Short end-to-end verifier: FAIL, `DATA/PIPELINE`/model-input readiness. The
  bounded run produced 49 verifier candidates, all negative, so verifier
  training correctly failed closed with `positive=0`.

Because the short end-to-end gate did not pass, the original implementation plan
is not resumed and full training remains blocked. No architecture or label
threshold change is authorized by this result.

## Artifacts

- [final event ledger](../artifacts/g1-participant-exclusion-eligibility-v3-final.json)
- [final cache directory](../artifacts/g1-formal-cache-v3-final)
- [representability audit](../artifacts/event-representability-v3-final.json)
- [G1 v3 coverage result](../artifacts/g1-candidate-coverage-v3.json)
- [small-set overfit result](../artifacts/small-set-overfit-v3-final.json)

Superseded artifacts are retained as historical evidence only: v2 eligibility,
old formal denominator, old label cache, old label statistics, and old fold
coverage results must not be consumed by downstream training/evaluation.

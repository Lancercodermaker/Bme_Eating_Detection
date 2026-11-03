# High-F1 Event Stack Full-Dataset Eligibility — Detailed Design Revision 2

日期：2026-09-15  
状态：Conditional design approval；`GO WITH RISKS`  
替代：`2026-09-15-high-f1-event-stack-participant-eligibility-design.md` 的 267-event denominator 部分  
模型架构：保持 frozen

## 1. Decision

formal target-train denominator 从单纯 file-level processed-only 扩展为 participant-level + event-level eligibility：

```text
file status == processed
AND participant has at least one processed session
AND event overlaps at least one processed indexed session
```

`AC3` 明确为 `ineligible_no_raw_session`。`HNU21018` 与 `HNU21042` 明确为 `ineligible_no_processed_session`。其他 participant 保留，但其不满足 event predicate 的标签只能进入 exclusion provenance，不能进入 G1 event denominator。

## 2. Source contract reconciliation

完整 source set 结果来自 `artifacts/g1-participant-exclusion-eligibility-v2.json`：

| Source | Count | Special difference |
|---|---:|---|
| user profile IDs, excluding test | 55 | 11 profile-only IDs |
| valid meal metadata IDs | 43 | includes AC3 |
| sensor original-data index IDs | 43 | matches organized raw IDs |
| organized raw audit IDs | 43 | includes 6C7 |
| union of sensor/raw/meal IDs | 44 | AC3 adds the 44th |
| raw/meal intersection | 42 | AC3 and 6C7 are the mismatch pair |

Source mismatches are not silently normalized. `meal_metadata_only`, `organized_raw_only`, `sensor_index_only` and `organized_raw_without_sensor_index` are all written to the artifact.

## 3. Participant eligibility

Participant status values:

```text
eligible
ineligible_no_processed_session
ineligible_no_raw_session
```

Expected status:

| Participant set | Status | Formal fold use |
|---|---|---|
| 41 raw participants with >=1 processed session | eligible | yes |
| HNU21018, HNU21042 | ineligible_no_processed_session | no |
| AC3 | ineligible_no_raw_session | no |
| 6C7 | eligible, zero valid meal events | yes, no positive event contribution |

`eligible` is determined by processed sensor sessions, not by event count. This preserves 6C7 as an auditable sensor participant without inventing labels.

## 4. Event eligibility

Every valid meal event gets exactly one status:

```text
usable_processed_overlap
overlap_only_invalid_sensor
no_index_session_overlap
metadata_only_no_session
```

Full counts:

| Event status | Count | Formal denominator |
|---|---:|---|
| usable_processed_overlap | 246 | yes |
| overlap_only_invalid_sensor | 20 | no |
| no_index_session_overlap | 12 | no |
| metadata_only_no_session | 3 | no |
| total valid metadata events | 281 | provenance only |

Participant-level event breakdown must remain available. The 20 invalid-overlap events include all 14 events from HNU21018/HNU21042 plus 6 events from otherwise eligible participants. The 12 no-index-overlap events remain event-level exclusions; their participants are not automatically removed.

Event denominator hash:

```text
1d98c9472a2904ec4c6507fd8792472ade84062f395f4fb4928656c1bd00d687
```

The hash is computed over canonical sorted event rows with status `usable_processed_overlap`.

## 5. Artifact contract

Primary artifact:

```text
artifacts/g1-participant-exclusion-eligibility-v2.json
```

Required fields:

- raw counts: discovered, processed, skipped and reason counts;
- participant source reconciliation and source file paths;
- participant status map and session counts;
- event status rows with participant, event index, interval and overlap counts;
- `manifest_sha256`;
- processed-file `denominator_sha256`;
- `event_denominator_sha256`;
- excluded participant IDs and event reason counts.

Formal G1 output must reference this artifact and copy all three hashes. A G1 result missing the event hash is diagnostic-only.

## 6. Pipeline boundary

### Before cache/fold

Use only file records with `status=processed` and participant status `eligible`. AC3 has no raw record and therefore cannot enter cache or fold. HNU21018/HNU21042 have only skipped records and therefore cannot enter cache or fold.

### During event truth attachment

Use only events with `usable_processed_overlap`. The existing session-bound intersection logic is the implementation reference; V2 must additionally compare its event count/hash with the eligibility artifact so an accidental denominator drift fails closed.

### During metrics

Compute coverage and event metrics over the 246-event effective denominator. Report excluded counts and reason distribution alongside metrics. Never report the 246-event metric as official hidden-test performance.

## 7. Validation gates

### V0 — full source-contract audit

Status: pass. Artifact has `1161/1127/34`, 44 source union participants, 281 total events, 246 usable events, 35 exclusions and all hashes.

### V1 — trusted baseline

Use the same baseline ID `m0-q50-groupnorm`, split seed `20260910`, valid fraction `0.20`, expected event F1 `0.17284`; replace only the participant input contract with the 41 eligible sensor participants and record the new eligibility/event hashes.

### V2 — formal G1

No file cap, all eligible processed records, 5 outer folds, frozen quantile grid `(0.70, 0.80, 0.90)`, no verifier. Every fold pooled coverage recall must be `>=0.90`.

### V3 — isolation

Verify no excluded participant/event appears in formal cache/fold/model/OOF/prediction/metric artifacts and that all excluded evidence remains in the eligibility artifact.

## 8. Failure and escalation

| Failure | Action |
|---|---|
| source set mismatch not represented in artifact | stop; `DATA_PIPELINE` |
| new unusable event class | stop; reopen Preflight |
| event hash mismatch | invalidate run; rebuild from eligibility artifact |
| excluded event enters metric | invalidate run; fix truth/denominator boundary |
| baseline participant/split mismatch | stop; `ASSUMPTION` |
| G1 fold `<0.90` | G1 fail; no verifier or Task 6+ |

No architecture reopen is allowed for denominator failures. Architecture remains frozen until a valid 246-event G1 produces evidence under this contract.

## 9. Decision

`GO WITH RISKS` for V1/V2/V3 only. The previous 267-event design is superseded. The next implementation must extend the formal G1 runner to consume and verify the v2 eligibility artifact before any fold metric is accepted.

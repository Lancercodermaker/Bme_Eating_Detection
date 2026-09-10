# Official submission runbook

The target-only submission runner trains on the labeled training participants and
emits predictions for the two official `test` sessions. It never loads meal
labels for `test`; the output contains only predicted intervals and provenance.

Use the controlled local configuration that was selected by participant-frozen
event-level experiments:

```powershell
& 'C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe' -u -m scripts.run_submission `
  --config configs/example.local.yaml `
  --cache-dir artifacts/candidate_cache_local10x2 `
  --window-seconds 15 `
  --step-seconds 7.5 `
  --candidate-threshold 0.2 `
  --candidate-fuse-gap-ms 300000 `
  --decode-fuse-gap-ms 600000 `
  --candidate-max-iter 100 `
  --verifier-max-iter 100 `
  --oof-folds 5 `
  --output artifacts/submission.json
```

For an isolated parser/output smoke test, add
`--max-files-per-participant 1` and use a separate output path. Do not use that
flag for the final training run. `--cache-only` is useful for checking that a
previously prepared cache is complete without rereading the raw files.

The runner reports `skipped_files` explicitly. A skipped file must be reviewed
before submission; malformed or timestamp-empty files are not silently treated
as negative examples. The official score is unavailable locally because the
organizer's test labels are not part of the allowed development data.

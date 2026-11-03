"""Read-only cache boundary/label audit; no raw access or model imports."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/a1-d3-boundary-contract-audit-v1'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def labels_for(starts, ends, truths):
    overlap = np.zeros(starts.size, dtype=np.int64)
    distance = np.full(starts.size, np.iinfo(np.int64).max, dtype=np.int64)
    for t in truths:
        a, b = t['start_ms'], t['end_ms']
        overlap = np.maximum(overlap, np.maximum(0, np.minimum(ends, b) - np.maximum(starts, a)))
        distance = np.minimum(distance, np.maximum(0, np.maximum(a - ends, starts - b)))
    return np.where(overlap * 2 >= ends - starts, 1, np.where(distance >= 300000, 0, -1))


def main():
    if OUT.exists():
        raise ValueError('Refusing to overwrite audit output')
    # Hand-computable checks include exact 50% overlap and 300s proximity.
    assert labels_for(np.array([0, 20000, 320000]), np.array([10000, 30000, 330000]),
                      [{'start_ms': 5000, 'end_ms': 20000}]).tolist() == [1, -1, 0]
    base = ROOT / 'artifacts/g1-candidate-coverage-v4'
    paths = {name: base / f'{name}.json' for name in ('cache-manifest', 'manifest-audit', 'eligibility')}
    data = {name: json.loads(path.read_text(encoding='utf-8')) for name, path in paths.items()}
    audit = defaultdict(list)
    for row in data['manifest-audit']['records']:
        audit[row.get('path_or_file_id')].append(row)
    truths = defaultdict(list)
    for row in data['eligibility']['event_eligibility']:
        if row['training_eligibility']:
            truths[row['participant_id']].append(row)
    totals = Counter()
    per_participant = defaultdict(Counter)
    entries = []
    affected_gt = set()
    for entry in data['cache-manifest']['entries']:
        matches = audit[entry['path']]
        assert len(matches) == 1 and matches[0]['status'] == 'processed'
        row = matches[0]
        assert row['participant_id'] == entry['participant_id'] and row['session_id'] == entry['session_id']
        path = Path(entry['cache_path'])
        path.resolve().relative_to((ROOT / 'artifacts/g1-formal-cache-v3-final').resolve())
        assert digest(path) == entry['cache_sha256']
        with np.load(path, allow_pickle=False) as z:
            starts, ends, labels = z['starts'], z['ends'], z['labels']
            assert len(starts) == len(ends) == len(labels)
            assert np.all(ends > starts)
            s, e = row['session_start_ms'], row['session_end_ms']
            before, after = starts < s, ends > e
            outside = before | after
            p = entry['participant_id']
            all_gt = truths[p]
            local_gt = [t for t in all_gt if t['start_ms'] < e and t['end_ms'] > s]
            local_labels = labels_for(starts, ends, local_gt)
            full_labels = labels_for(starts, ends, all_gt)
            change = full_labels != local_labels
            counts = Counter(entries=1, windows=len(starts), out_of_bounds_entries=int(outside.any()),
                             out_of_bounds_windows=int(outside.sum()), before_windows=int(before.sum()),
                             after_windows=int(after.sum()), cached_vs_local_mismatch=int((labels != local_labels).sum()),
                             cached_vs_participant_mismatch=int((labels != full_labels).sum()),
                             local_vs_participant_changes=int(change.sum()),
                             changed_outside_windows=int((change & outside).sum()),
                             crossed_gap_windows=int(z['crosses_gap'].sum()),
                             coverage_below_point8=int((z['coverage'] < 0.8).sum()),
                             invalid_run_above20=int((z['invalid_runs'] > 20).sum()))
            for value, name in ((1, 'positive'), (0, 'negative'), (-1, 'ignore')):
                counts[f'outside_{name}'] = int((outside & (labels == value)).sum())
            near = np.zeros(starts.size, dtype=bool)
            intersects = np.zeros(starts.size, dtype=bool)
            for t in all_gt:
                overlap = (starts < t['end_ms']) & (ends > t['start_ms'])
                proximity = np.maximum(0, np.maximum(t['start_ms'] - ends, starts - t['end_ms'])) < 300000
                near |= proximity
                intersects |= overlap
                if (outside & overlap).any():
                    affected_gt.add((p, t['event_index']))
            counts['outside_overlapping_training_gt'] = int((outside & intersects).sum())
            counts['outside_within300s_training_gt'] = int((outside & near).sum())
            transitions = Counter(f'{int(a)}->{int(b)}' for a, b in zip(labels[change], full_labels[change]))
            totals.update(counts)
            per_participant[p].update(counts)
            entries.append(dict(record_id=path.stem, participant_id=p, session_id=entry['session_id'],
                                cache_sha256=entry['cache_sha256'], index_start_ms=s, index_end_ms=e,
                                counts=dict(counts), max_start_underflow_ms=int(max(0, s - starts.min())) if starts.size else 0,
                                max_end_overflow_ms=int(max(0, ends.max() - e)) if ends.size else 0,
                                label_transitions=dict(transitions),
                                changed_rows=np.flatnonzero(change).tolist()))
    result = dict(status='AUDIT_COMPLETED_NOT_A1_READY', fit_count=0, predict_count=0,
                  raw_sensor_io=False, external_data_io=False, official_test_io=False,
                  method='Independent vectorized label replay: overlap>=0.5; negative distance>=300000ms',
                  input_hashes={name: digest(path) for name, path in paths.items()},
                  script_sha256=digest(Path(__file__)), totals=dict(totals),
                  participants=len(per_participant),
                  affected_gt_overlapped_by_outside_windows=sorted(affected_gt),
                  max_start_underflow_ms=max(x['max_start_underflow_ms'] for x in entries),
                  max_end_overflow_ms=max(x['max_end_overflow_ms'] for x in entries),
                  per_participant={p: dict(c) for p, c in per_participant.items()}, entries=entries)
    OUT.mkdir()
    target = OUT / 'boundary-audit.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'boundary-audit.sha256').write_text(digest(target) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('entries', 'per_participant')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

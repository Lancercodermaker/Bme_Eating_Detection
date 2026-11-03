from dataclasses import replace
import hashlib
import json
import numpy as np
import pytest
from test_a1_inputs import write_fixture
from eating_event.a1.inputs import load_inputs


def revised_fixture(tmp_path):
    root, config = write_fixture(tmp_path)
    cp = root / 'artifacts/g1-formal-cache-v3-final/record-a.npz'
    with np.load(cp, allow_pickle=True) as z:
        values = {k: z[k] for k in z.files}
    values['session_ids'] = np.array(['', ''])
    values['metadata'] = np.asarray(json.dumps({'cache_key': 'record-a'}), dtype=object)
    np.savez_compressed(cp, **values)
    mp = root/'artifacts/cache-manifest.json'
    m = json.loads(mp.read_text());m['entries'][0]['cache_sha256'] = hashlib.sha256(cp.read_bytes()).hexdigest()
    mp.write_text(json.dumps(m))
    ap = root/'artifacts/manifest-audit.json';a = json.loads(ap.read_text())
    a['records'][0]['session_start_ms'] = 1000
    ap.write_text(json.dumps(a))
    return root, replace(config, d3_revision='D3-Ready-v1'), cp


def test_approved_identity_boundary_and_labels_do_not_rewrite_npz(tmp_path):
    root, config, cp = revised_fixture(tmp_path)
    before = cp.read_bytes()
    bundle = load_inputs(root, config)
    assert cp.read_bytes() == before
    assert bundle.windows[0].identity.session_id == 's1'
    assert bundle.windows[0].start_ms == 0
    assert [w.label for w in bundle.windows] == [1, -1]
    assert bundle.identity_audit[0]['session_identity_source'] == 'approved_cache_manifest_v1'
    assert len(bundle.label_changes) == 2


def test_duplicate_audit_mapping_is_rejected(tmp_path):
    root, config, _ = revised_fixture(tmp_path)
    p=root/'artifacts/manifest-audit.json'; x=json.loads(p.read_text());x['records']*=2;p.write_text(json.dumps(x))
    with pytest.raises(ValueError, match='duplicate'):
        load_inputs(root, config)

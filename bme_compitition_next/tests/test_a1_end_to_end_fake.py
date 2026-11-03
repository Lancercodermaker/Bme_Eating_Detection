from dataclasses import asdict
import json
import numpy as np
from eating_event.a1.contracts import A1Config, WindowIdentity
from eating_event.a1.inputs import A1Window, InputBundle, TruthRecord
from eating_event.a1.pipeline import build_role_graph, execute_full_pipeline
from eating_event.metrics import EventInterval


class FakeModel:
    def predict_proba(self, x):
        return np.tile([.1, .9], (len(x), 1))


class FakeBackend:
    def __init__(self):
        self.fits = []

    def fit(self, kind, x, y, participants, config):
        self.fits.append((kind, tuple(sorted(set(participants)))))
        return FakeModel()


def bundle():
    windows, entries, truths = [], [], {}
    for pi in range(41):
        p = f'p{pi:02d}'
        truths[p] = (TruthRecord(p, p, EventInterval(0, 232500)),)
        for ri in range(2):
            r = f'{p}-{ri}'; offset = ri*1000000
            entries.append({'participant_id': p})
            for i in range(30):
                windows.append(A1Window(WindowIdentity(p,r,r,i), offset+i*7500,
                                        offset+i*7500+15000,1,False,np.full(111,pi,dtype=np.float32),
                                        1 if ri==0 else 0,offset,offset+300000))
    return InputBundle(tuple(windows),truths,tuple(entries),{}, {}, {},training_truths=truths)


def test_real_orchestrator_with_fake_models_has_complete_provenance(tmp_path):
    data = bundle(); backend = FakeBackend()
    roles = build_role_graph(data.participants)
    (tmp_path/'role-graph.json').write_text(json.dumps([asdict(r) for r in roles]))
    result = execute_full_pipeline(data,A1Config(),tmp_path,backend=backend)
    assert result['status'] == 'COMPLETE', result
    assert len(backend.fits) == 130
    assert result['quality']['numeric_minimum']
    assert len(result['participant_metrics']) == 41
    assert result['outer_results'][0]['candidate_count'] > 0
    assert result['outer_results'][0]['candidate_covered_gt'] > 0
    assert result['macro_event_bearing_f1'] is not None
    lines=[json.loads(s) for s in (tmp_path/'score-provenance.jsonl').read_text().splitlines()]
    assert len(lines) == 130
    for row in lines:
        assert not set(row['fit_participants']) & set(row['scored_participants'])
        assert row['model_hash'] and row['fit_signature'] and row['score_file_sha256']
    assert (tmp_path/'report.md').exists()


def test_outer_truth_changes_do_not_change_that_folds_prediction_or_selection(tmp_path):
    from dataclasses import replace
    data=bundle(); roles=build_role_graph(data.participants)
    baseline_dir=tmp_path/'baseline';changed_dir=tmp_path/'changed'
    for d in (baseline_dir,changed_dir):
        d.mkdir();(d/'role-graph.json').write_text(json.dumps([asdict(r) for r in roles]))
    baseline=execute_full_pipeline(data,A1Config(),baseline_dir,backend=FakeBackend())
    first=next(r for r in roles if r.role_id=='candidate/outer-0/outer')
    altered=dict(data.truths)
    for p in first.scored_participants:
        altered[p]=(TruthRecord(p,p,EventInterval(5000000,5232500)),)
    changed=execute_full_pipeline(replace(data,truths=altered,training_truths=altered),A1Config(),changed_dir,backend=FakeBackend())
    assert baseline['outer_results'][0]['selected_threshold']==changed['outer_results'][0]['selected_threshold']
    def first_predictions(d):
        return [json.loads(line) for line in (d/'predictions.jsonl').read_text().splitlines() if json.loads(line)['outer_fold']=='outer-0']
    assert first_predictions(baseline_dir)==first_predictions(changed_dir)


def test_g3_failure_stops_before_verifier_fit(tmp_path):
    from dataclasses import replace
    data=bundle();roles=build_role_graph(data.participants);backend=FakeBackend()
    (tmp_path/'role-graph.json').write_text(json.dumps([asdict(r) for r in roles]))
    result=execute_full_pipeline(replace(data,training_truths={}),A1Config(),tmp_path,backend=backend)
    assert result['status']=='VERIFIER_DATA_INSUFFICIENT'
    assert len(backend.fits)==4
    assert all(kind=='candidate' for kind,_ in backend.fits)


def test_runner_executes_snapshot_and_checks_audit_integrity(tmp_path, monkeypatch):
    import pytest
    from pathlib import Path
    from scripts import run_a1_feasibility as runner
    from eating_event.a1 import pipeline
    data=bundle();backend=FakeBackend()
    config=tmp_path/'config.json';config.write_text('{}')
    roles=build_role_graph(data.participants)
    runner._write_json(tmp_path/'role-graph.json',[asdict(r) for r in roles])
    audit={'status':'READY','source_hashes':{},'code_identity':runner._code_identity(tmp_path,config)}
    runner._write_json(tmp_path/'input-audit.json',audit)
    manifest={'config_sha256':runner._sha256_file(config),'input_audit_sha256':runner._sha256_file(tmp_path/'input-audit.json'),
              'environment':runner.environment_identity(),'artifact_hashes':{'role-graph.json':runner._sha256_file(tmp_path/'role-graph.json')}}
    runner._write_json(tmp_path/'run-manifest.json',manifest)
    monkeypatch.setattr(runner,'verify_inputs',lambda *args:None)
    monkeypatch.setattr(runner,'verify_bundle',lambda *args:None)
    monkeypatch.setattr(runner,'load_inputs',lambda *args:data)
    original=pipeline.execute_full_pipeline
    monkeypatch.setattr(pipeline,'execute_full_pipeline',lambda b,c,d: original(b,c,d,backend=backend))
    result=runner._execute_work(config,tmp_path,root=tmp_path)
    assert result['status']=='COMPLETE'
    assert (tmp_path/'final-checksums.json').exists()
    audit['note']='tampered';runner._write_json(tmp_path/'input-audit.json',audit)
    with pytest.raises(ValueError,match='audit digest'):
        runner._execute_work(config,tmp_path,root=tmp_path)

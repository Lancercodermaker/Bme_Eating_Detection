import json
import pytest
from scripts import run_a1_feasibility as runner


def test_completed_run_is_rejected_before_loading_inputs(tmp_path):
    d=tmp_path/'run';d.mkdir()
    (d/'run-status.json').write_text(json.dumps({'status':'COMPLETE'}))
    with pytest.raises(ValueError,match='state|completed|terminal'):
        runner.execute_run(tmp_path/'config.json',d)


def test_audit_failure_cannot_write_into_existing_directory(tmp_path):
    d=tmp_path/'run';d.mkdir();(d/'sentinel').write_text('original')
    result=runner.main(['--mode','audit','--config',str(tmp_path/'missing.json'),'--run-dir',str(d)])
    assert result != 0
    assert sorted(p.name for p in d.iterdir()) == ['sentinel']


def test_production_anchor_rejects_unapproved_manifest(tmp_path):
    from eating_event.a1 import anchors
    from eating_event.a1.contracts import A1Config
    with pytest.raises(ValueError,match='approved|hash|revision'):
        anchors.verify_inputs(tmp_path,A1Config())


def test_new_run_cannot_reset_prior_fit_attempts(tmp_path):
    from eating_event.a1.control import launch
    artifacts=tmp_path/'artifacts';artifacts.mkdir()
    old=artifacts/'a1-end-to-end-feasibility-v1-old';old.mkdir()
    (old/'fit-ledger.jsonl').write_text(json.dumps({'event':'reserve','kind':'candidate','role_id':'r'})+'\n')
    new=artifacts/'a1-end-to-end-feasibility-v1-new';new.mkdir()
    (new/'run-status.json').write_text(json.dumps({'status':'AUDIT_READY'}))
    with pytest.raises(ValueError,match='prior fit'):
        launch('run',tmp_path/'config.json',new,tmp_path,{})

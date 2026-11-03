"""Single-owner study budget and supervised audit/run state transitions."""
from dataclasses import asdict
from pathlib import Path
import json
import os
import sys
import time
from .budget import BudgetLimits, ResourceNotReady, run_supervised
from .execution import write_json


def launch(mode, config_path, run_dir, root, resources):
    run_dir=Path(run_dir).resolve();root=Path(root).resolve()
    artifacts=root/'artifacts'
    artifacts.mkdir(exist_ok=True)
    # Only the dedicated new study namespace may be mutated.
    if run_dir.parent != artifacts or not run_dir.name.startswith('a1-end-to-end-feasibility-v1-'):
        raise ValueError('run directory must be a new A1 study directory')
    lock=artifacts/'a1-study.lock'
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError('study already running or interrupted; inspect lock before recovery') from exc
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    started=time.monotonic()
    study=artifacts/'a1-study-budget.jsonl'
    try:
        records=[json.loads(line) for line in study.read_text().splitlines()] if study.exists() else []
        # Old failed audits did not measure elapsed time. Conservatively debit
        # their full approved audit ceiling once, rather than assuming zero.
        accounted={r.get('run_dir') for r in records}
        for old in sorted(artifacts.glob('a1-end-to-end-feasibility-v1-*')):
            if (old/'audit-failure.json').exists() and str(old) not in accounted:
                row=dict(run_dir=str(old),mode='historical_audit_upper_bound',charged_seconds=1800)
                records.append(row)
                with study.open('a') as stream: stream.write(json.dumps(row)+'\n')
        prior=sum(float(r['charged_seconds']) for r in records)
        if prior >= 21600:
            raise ResourceNotReady('cumulative study wall budget exhausted')
        if mode=='audit':
            run_dir.mkdir(exist_ok=False)
            write_json(run_dir/'startup-resources.json',resources)
            limits=BudgetLimits(max_rss_bytes=resources['max_rss_bytes'])
            write_json(run_dir/'limits.json',asdict(limits))
        else:
            prior_fits = 0
            for fit_log in artifacts.glob('a1-end-to-end-feasibility-v1-*/fit-ledger.jsonl'):
                prior_fits += sum(json.loads(line).get('event') == 'reserve' for line in fit_log.read_text().splitlines() if line.strip())
            if prior_fits:
                raise ValueError('prior fit attempts exist; explicit checkpoint recovery required, never restart from a new run')
            state=json.loads((run_dir/'run-status.json').read_text())
            if state.get('status')!='AUDIT_READY':
                raise ValueError('terminal run state; implicit retry/resume forbidden')
            limits=BudgetLimits(**json.loads((run_dir/'limits.json').read_text()))
        request=dict(mode=mode,config_path=str(Path(config_path).resolve()),run_dir=str(run_dir),root=str(root))
        write_json(run_dir/'worker-request.json',request)
        write_json(run_dir/'run-status.json',dict(status='AUDITING' if mode=='audit' else 'RUNNING'))
        error=None
        try:
            telemetry=run_supervised([sys.executable,'-m','eating_event.a1.worker',str(run_dir/'worker-request.json')],
                                     run_dir,limits,prior_seconds=prior,audit=mode=='audit')
            response=run_dir/'worker-response.json'
            if not response.exists():
                raise ValueError(f'worker failed without response, exit={telemetry["returncode"]}')
            result=json.loads(response.read_text())
            if telemetry['returncode'] != 0 and result.get('status') in ('READY','COMPLETE'):
                raise ValueError('worker exit/status mismatch')
        except Exception as exc:
            error=str(exc)
            result=dict(status='NOT_READY' if mode=='audit' else ('INCOMPLETE_RESOURCE' if isinstance(exc,ResourceNotReady) else 'INVALID'),reason=error)
        finally:
            with study.open('a') as stream:
                stream.write(json.dumps(dict(run_dir=str(run_dir),mode=mode,charged_seconds=time.monotonic()-started,error=error))+'\n')
        status=result['status']
        write_json(run_dir/'run-status.json',dict(status='AUDIT_READY' if status=='READY' else status))
        if mode=='audit' and status!='READY':
            write_json(run_dir/'audit-failure.json',dict(result,fit_count=0,predict_count=0))
        if mode=='run':
            write_json(run_dir/'metrics.json',result)
        return result
    finally:
        lock.unlink()

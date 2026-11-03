"""Private subprocess entry; the parent owns limits and final run status."""
import json
from pathlib import Path
import sys
from .execution import write_json


def main():
    request=json.loads(Path(sys.argv[1]).read_text())
    output=Path(request['run_dir'])
    try:
        from scripts.run_a1_feasibility import _audit_work, _execute_work
        function=_audit_work if request['mode']=='audit' else _execute_work
        result=function(Path(request['config_path']),output,root=Path(request['root']))
    except Exception as exc:
        result=dict(status='NOT_READY' if request['mode']=='audit' else 'INVALID',reason=f'{type(exc).__name__}: {exc}')
    write_json(output/'worker-response.json',result)
    return 0 if result.get('status') in ('READY','COMPLETE') else 2


if __name__=='__main__':
    raise SystemExit(main())

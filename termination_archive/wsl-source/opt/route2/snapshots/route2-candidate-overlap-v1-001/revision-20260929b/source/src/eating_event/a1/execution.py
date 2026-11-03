"""Execute only a frozen role snapshot; retain actual model/score lineage."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import pickle
import time
import numpy as np

from .budget import BudgetLedger, BudgetLimits, ResourceNotReady
from .contracts import stable_hash, require_disjoint
from .events import build_candidates, label_candidates, decode_candidates
from .metrics import PredictionRecord, evaluate_participants, evaluate_quality
from eating_event.metrics import interval_iou
from .scoring import fit_candidate_estimator, fit_verifier_estimator, compute_reference_threshold, validate_g3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


class Backend:
    def fit(self, kind, x, y, participants, config):
        args = dict(positive_weight=3., random_state=config.seed, max_iter=100)
        if kind == 'candidate':
            return fit_candidate_estimator(x, y, **args)
        return fit_verifier_estimator(x, y, participants, **args)


class Execution:
    def __init__(self, bundle, config, output, backend, limits):
        self.bundle, self.config, self.output = bundle, config, Path(output)
        self.backend = backend
        self.ledger = BudgetLedger(self.output/'fit-ledger.jsonl', limits)
        self.rows = {w.identity.stable_id: i for i,w in enumerate(bundle.windows)}
        self.append_count = 0
        manifest_path = self.output/'run-manifest.json'
        self.run_identity = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'synthetic_backend': True}
        write_json(self.output/'window-identity.json', [asdict(w.identity) for w in bundle.windows])
        for name in ('models', 'scores'):
            (self.output/name).mkdir(exist_ok=True)

    def append(self, filename, row):
        with (self.output/filename).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
        self.append_count += 1
        if self.append_count % 100 == 0:
            self.ledger.check_output_size(self.output)

    def fit(self, items, role):
        kind = role.kind
        participants = [w.identity.participant_id if kind=='candidate' else w.participant_id for w in items]
        if not set(participants) <= set(role.fit_participants):
            raise ValueError('fit rows outside role participants')
        require_disjoint(participants, role.outer_valid)
        x = np.asarray([w.features for w in items], dtype=np.float32)
        y = np.asarray([w.label for w in items], dtype=np.int8)
        if kind == 'verifier':
            try:
                validate_g3(y, participants)
            except ValueError as exc:
                raise ValueError(f'G3: {exc}') from exc
        ids = [w.identity.stable_id if kind=='candidate' else w.candidate_id for w in items]
        info = dict(role_id=role.role_id, kind=kind, fit_participants=list(role.fit_participants),
                    fit_row_hash=stable_hash(ids), features_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
                    labels_sha256=hashlib.sha256(y.tobytes()).hexdigest(),
                    parameters=dict(self.config.candidate_hgb if kind=='candidate' else self.config.verifier_hgb),
                    input_hashes=dict(self.bundle.source_hashes), run_identity=self.run_identity,
                    feature_schema=self.config.feature_schema, label_schema='participant_training_truth_labels_v1')
        if kind == 'verifier':
            positive_gt = {(c.participant_id,t.event_id) for c in items if c.label==1
                           for t in self.bundle.training_truths.get(c.participant_id,())
                           if interval_iou(c.interval,t.interval) > .25}
            info['positive_candidate_count'] = int((y == 1).sum())
            info['positive_participant_count'] = len({p for p,label in zip(participants,y) if label==1})
            info['positive_unique_gt_count'] = len(positive_gt)
        info['fit_signature'] = stable_hash(info)
        self.ledger.reserve_fit(kind, role.role_id)
        started = time.monotonic()
        write_json(self.output/'phase.json', dict(kind='fit', role=role.role_id, started_at=time.time()))
        try:
            model = self.backend.fit(kind,x,y,participants,self.config)
            blob = pickle.dumps(model, protocol=5)
            info['model_hash'] = hashlib.sha256(blob).hexdigest()
            path = self.output/'models'/f'{info["fit_signature"]}.pickle'
            if path.exists():
                raise ValueError('duplicate fit artifact')
            path.write_bytes(blob)
            self.ledger.record_fit_result(role.role_id,'success',elapsed_seconds=time.monotonic()-started)
        except Exception as exc:
            self.ledger.record_fit_result(role.role_id,'failed',elapsed_seconds=time.monotonic()-started,error=str(exc))
            raise
        finally:
            write_json(self.output/'phase.json',dict(kind='processing'))
        self.append('model-provenance.jsonl',info)
        return model,info

    def score(self, handle, items, role, *, reference=None):
        model, info = handle
        kind = role.kind
        participants = [w.identity.participant_id if kind=='candidate' else w.participant_id for w in items]
        require_disjoint(info['fit_participants'], participants)
        if not set(participants) <= set(role.scored_participants):
            raise ValueError('scored rows outside frozen role')
        x = np.asarray([w.features for w in items],dtype=np.float32)
        raw = np.asarray(model.predict_proba(x)[:,1],dtype=np.float64) if items else np.empty(0)
        if raw.shape != (len(items),) or not np.isfinite(raw).all():
            raise ValueError('invalid model scores')
        ids = [self.rows[w.identity.stable_id] if kind=='candidate' else w.candidate_id for w in items]
        threshold = reference.threshold if reference else 0.
        score_path = self.output/'scores'/f'{stable_hash(role.role_id)}.npz'
        np.savez_compressed(score_path, ids=np.asarray(ids), raw=raw, relative=raw-threshold)
        provenance = dict(info, scored_participants=list(role.scored_participants),
                          selection_participants=list(role.selection_participants),
                          threshold_reference_participants=list(role.reference_participants) if reference else [],
                          reference_row_hash=reference.row_hash if reference else None,
                          reference_count=reference.row_count if reference else 0,
                          threshold=threshold if reference else None, q=self.config.candidate_quantile if reference else None,
                          score_file=str(score_path.relative_to(self.output)),score_file_sha256=sha(score_path),
                          outer_valid=list(role.outer_valid))
        self.append('score-provenance.jsonl',provenance)
        return raw

    def candidates(self, fit_rows, target_rows, role, *, label):
        handle = self.fit(fit_rows,role)
        model,_ = handle
        ref_scores = model.predict_proba(np.asarray([w.features for w in fit_rows],dtype=np.float32))[:,1]
        reference = compute_reference_threshold(ref_scores,[w.label for w in fit_rows],self.config.candidate_quantile,
                                                row_ids=[w.identity.stable_id for w in fit_rows])
        scores = self.score(handle,target_rows,role,reference=reference)
        groups = {}
        for w,score in zip(target_rows,scores):
            groups.setdefault((w.identity.participant_id,w.identity.record_id,w.identity.session_id),[]).append((w,score))
        result=[]
        for key, pairs in sorted(groups.items()):
            generated=build_candidates([w for w,_ in pairs],[s for _,s in pairs],
                                       threshold_reference=reference.threshold,fuse_gap_ms=self.config.candidate_fuse_ms)
            if label:
                gt = self.bundle.training_truths.get(key[0],())
                generated=label_candidates(generated,[t.interval for t in gt])
            result.extend(generated)
            for c in generated:
                row=asdict(c);row['features']=c.features.tolist();row['role_id']=role.role_id
                self.append('event-candidates.jsonl',row)
        return result


def execute(bundle, config, run_dir, *, backend=None):
    from .pipeline import Role, validate_role_graph
    output=Path(run_dir)
    roles=[]
    for row in json.loads((output/'role-graph.json').read_text(encoding='utf-8')):
        for key in ('fit_participants','reference_participants','scored_participants','selection_participants','outer_valid','thresholds'):
            row[key]=tuple(row[key])
        roles.append(Role(**row))
    validate_role_graph(roles,bundle.participants)
    limits_path=output/'limits.json'
    limits=BudgetLimits(**json.loads(limits_path.read_text())) if limits_path.exists() else BudgetLimits()
    # CLI production execution always supplies limits + supervisor; fake backends are test injection only.
    if backend is None and not limits_path.exists():
        raise ValueError('supervised run limits missing')
    engine=Execution(bundle,config,output,backend or Backend(),limits)
    role_index={r.role_id:r for r in roles}
    outer_roles=sorted((r for r in roles if r.kind=='candidate' and r.inner_fold is None),key=lambda r:r.outer_fold)
    def rows(participants):
        return tuple(w for w in bundle.windows if w.identity.participant_id in set(participants))
    def truth(participants):
        return [t for p in participants for t in bundle.truths.get(p,())]
    def decode(candidates,scores,threshold):
        return [PredictionRecord.from_decoded(p) for p in decode_candidates(candidates,scores,threshold=threshold,
                min_duration_ms=config.min_duration_ms,decode_fuse_gap_ms=config.decode_fuse_ms)]
    all_predictions=[]; fold_metrics=[]; outer_results=[]
    try:
        for outer in outer_roles:
            inner_roles=sorted((r for r in roles if r.kind=='candidate' and r.outer_fold==outer.outer_fold and r.inner_fold is not None and r.subinner_fold is None),key=lambda r:r.inner_fold)
            predictions_by_threshold={t:[] for t in config.verifier_thresholds}
            outer_oof=[]
            for inner in inner_roles:
                sub_roles=[r for r in roles if r.kind=='candidate' and r.outer_fold==outer.outer_fold and r.inner_fold==inner.inner_fold and r.subinner_fold is not None]
                train_candidates=[]
                for sub in sub_roles:
                    train_candidates.extend(engine.candidates(rows(sub.fit_participants),rows(sub.scored_participants),sub,label=True))
                verifier_role=role_index[f'verifier/{outer.outer_fold}/{inner.inner_fold}']
                verifier=engine.fit(train_candidates,verifier_role)
                valid_candidates=engine.candidates(rows(inner.fit_participants),rows(inner.scored_participants),inner,label=True)
                outer_oof.extend(valid_candidates)
                scores=engine.score(verifier,valid_candidates,verifier_role)
                for threshold in config.verifier_thresholds:
                    predictions_by_threshold[threshold].extend(decode(valid_candidates,scores,threshold))
            selection=[]
            for threshold,predictions in predictions_by_threshold.items():
                metric=evaluate_participants(predictions,truth(outer.fit_participants),participant_ids=outer.fit_participants)
                selection.append((metric.f1 if metric.f1 is not None else -1.,-metric.fp,threshold))
            selected=max(selection)[2]
            engine.append('threshold-selection.jsonl',dict(outer_fold=outer.outer_fold,selected=selected,results=selection,
                                                           selection_participants=list(outer.fit_participants)))
            vrole=role_index[f'verifier/{outer.outer_fold}/outer']
            verifier=engine.fit(outer_oof,vrole)
            candidates=engine.candidates(rows(outer.fit_participants),rows(outer.scored_participants),outer,label=False)
            scores=engine.score(verifier,candidates,vrole)
            predictions=decode(candidates,scores,selected)
            metric=evaluate_participants(predictions,truth(outer.scored_participants),participant_ids=outer.scored_participants)
            fold_metrics.append(metric);all_predictions.extend(predictions)
            covered = sum(any(c.participant_id==t.participant_id and interval_iou(c.interval,t.interval)>.25 for c in candidates)
                          for t in truth(outer.scored_participants))
            outer_results.append(dict(fold_id=outer.outer_fold,selected_threshold=selected,
                                      candidate_count=len(candidates),prediction_count=len(predictions),
                                      candidate_covered_gt=covered,
                                      structurally_short_gt_count=sum(t.interval.end_ms-t.interval.start_ms<=45000 for t in truth(outer.scored_participants)),
                                      **asdict(metric)))
            for p in predictions:
                engine.append('predictions.jsonl',dict(outer_fold=outer.outer_fold,**asdict(p)))
        pooled=evaluate_participants(all_predictions,truth(bundle.participants),participant_ids=bundle.participants)
        quality=evaluate_quality(fold_metrics,outer_fold_f1=[m.f1 for m in fold_metrics],pooled=pooled)
        result=dict(status='COMPLETE',pooled_f1=pooled.f1,pooled=asdict(pooled),outer_results=outer_results,
                    participant_metrics=[asdict(p) for p in pooled.participants],quality=asdict(quality),
                    macro_event_bearing_f1=float(np.mean([p.f1 for p in pooled.participants if p.tp+p.fn])) if any(p.tp+p.fn for p in pooled.participants) else None,
                    fit_attempts=asdict(engine.ledger.state()),interpretation='development only; no independent confirmation')
        write_json(output/'matches.json',[asdict(p) for p in pooled.participants])
        (output/'report.md').write_text('# A1 development result\n\n'+json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return result
    except ResourceNotReady as exc:
        return dict(status='INCOMPLETE_RESOURCE',reason=str(exc),outer_results=outer_results)
    except Exception as exc:
        return dict(status='VERIFIER_DATA_INSUFFICIENT' if str(exc).startswith('G3:') else 'INVALID',reason=str(exc),outer_results=outer_results)

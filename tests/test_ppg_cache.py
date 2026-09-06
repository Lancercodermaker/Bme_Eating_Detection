import importlib
import importlib.util
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest


def test_ppg_cache_api_exists():
    assert importlib.util.find_spec('eating_detection.ppg_cache') is not None, 'PPG cache is not implemented'


@pytest.fixture
def mod():
    assert importlib.util.find_spec('eating_detection.ppg_cache') is not None, 'PPG cache is not implemented'
    return importlib.import_module('eating_detection.ppg_cache')


def write_source(path, times=(1000, 1100, 1200, 1300), values=None, channels=44):
    path.parent.mkdir(parents=True, exist_ok=True)
    values = values if values is not None else np.full((len(times), channels), 2.)
    lines = ['\t'.join(['PPG_TIME'] + [f'PPG{i}' for i in range(1, channels + 1)])]
    lines += ['\t'.join(map(str, [t, *row[:channels]])) for t, row in zip(times, values)]
    path.write_text('\n'.join(lines) + '\n')
    return path


def config(mod, **kw):
    return mod.PPGCacheConfig(**dict(resample_hz=10, window_sec=.2, step_sec=.1, **kw))


@pytest.mark.parametrize('with_ppg',[False,True])
@pytest.mark.parametrize('boundary_mode',['soft','ignore'])
def test_shapes_labels_reference_and_independent_m0(mod, tmp_path, with_ppg, boundary_mode):
    from eating_detection.cache import FeatureCacheConfig, build_feature_cache
    path = tmp_path / 'p1' / 'sensor.txt'
    path.parent.mkdir()
    header = ['ACC_TIME', 'GYRO_TIME', 'ACC_X', 'ACC_Y', 'ACC_Z', 'GYRO_X', 'GYRO_Y', 'GYRO_Z']
    if with_ppg:
        header += ['PPG_TIME']+[f'PPG{i}' for i in range(1,45)]
    path.write_text('\t'.join(header) + '\n' + '\n'.join('\t'.join(map(str, [1000+i*100]*2+[1]*6+([1000+i*100]+[i+1]*44 if with_ppg else []))) for i in range(31)))
    root = tmp_path / 'cache'
    imu = build_feature_cache(path, [(1500, 2500)], root, FeatureCacheConfig(resample_hz=25, window_sec=1, step_sec=1,boundary_mode=boundary_mode))
    before = imu.cache_path.read_bytes()
    ppg = mod.build_ppg_cache(path, [(1500, 2500)], root, mod.PPGCacheConfig(resample_hz=25, window_sec=1, step_sec=1,boundary_mode=boundary_mode), imu.timestamps_ms)
    for name in ('timestamps_ms', 'window_indices', 'window_starts_ms', 'window_ends_ms', 'window_labels', 'window_loss_mask'):
        np.testing.assert_array_equal(getattr(ppg, name), getattr(imu, name))
    assert ppg.features.shape == (45, len(imu.timestamps_ms))
    assert ppg.quality_mask.shape == (1, len(imu.timestamps_ms))
    assert bool(ppg.features.any()) == with_ppg
    assert ppg.features.dtype == np.float32 and ppg.features.flags.c_contiguous
    assert ppg.quality_mask.dtype == bool and ppg.window_indices.dtype == np.int64
    assert ppg.cache_path != imu.cache_path and imu.cache_path.read_bytes() == before


@pytest.mark.parametrize('kind', ['empty', 'partial', 'zero', 'nonfinite'])
def test_unobservable_ppg_retains_reference(mod, tmp_path, kind):
    values = np.zeros((4, 44)) if kind == 'zero' else np.full((4, 44), np.nan)
    path = write_source(tmp_path / 'x', times=() if kind == 'empty' else (1000,1100,1200,1300), values=values, channels=43 if kind == 'partial' else 44)
    ref = np.arange(900, 1500, 100, dtype=np.int64)
    cache = mod.build_ppg_cache(path, [], tmp_path / 'cache', config(mod), ref)
    assert cache.features.shape == (45, 6) and not cache.features.any()
    assert not cache.quality_mask.any()


def test_duplicate_invalid_rows_are_barriers_and_zero_time_ignored(mod, tmp_path):
    times = [0, 1000, 1000, 1100, 1200, 1300]
    values = np.full((6,44), 2.)
    values[0] = 999; values[2] = 4; values[3] = np.nan; values[4] = 0
    path = write_source(tmp_path/'x', times, values)
    ref = np.arange(900, 1500, 100, dtype=np.int64)
    cache = mod.build_ppg_cache(path, [], tmp_path/'cache', config(mod,flat_policy='keep'), ref)
    np.testing.assert_array_equal(cache.quality_mask[0], [False,True,False,False,True,False])
    np.testing.assert_allclose(cache.features[:44,1], 3)
    assert np.isfinite(cache.features).all()
    assert not cache.features[:44, ~cache.quality_mask[0]].any()


def test_uniform_interpolation_precedes_resampling(mod, tmp_path, monkeypatch):
    path = write_source(tmp_path/'x', [1000,1100,1300], np.tile([1.,2.,4.], (44,1)).T)
    seen=[]
    real=mod.resample_uniform
    def spy(values, source_hz, target_hz):
        seen.append((values.copy(), source_hz, target_hz))
        return real(values, source_hz, target_hz)
    monkeypatch.setattr(mod, 'resample_uniform', spy)
    cache=mod.build_ppg_cache(path, [], tmp_path/'cache', config(mod))
    assert seen and seen[0][0].shape[1] == 44
    np.testing.assert_allclose(seen[0][0][:,0], [1,2.5,4])
    assert seen[0][1] == pytest.approx(1000/150)
    assert cache.timestamps_ms[0] == 1000


def test_hit_never_reads_csv_and_lazy_loads(mod, tmp_path, monkeypatch):
    path=write_source(tmp_path/'x')
    first=mod.build_ppg_cache(path, [], tmp_path/'cache', config(mod))
    def fail(*a,**kw): raise AssertionError('raw CSV was opened')
    monkeypatch.setattr(mod, 'iter_ppg_chunks', fail)
    monkeypatch.setattr('pandas.read_csv', fail)
    hit=mod.build_ppg_cache(path, [], tmp_path/'cache', config(mod), lazy=True)
    assert hit.cache_hit and not hit.features_loaded
    np.testing.assert_array_equal(hit.features,first.features)
    hit.release_features()
    assert not hit.features_loaded


def test_key_sensitive_to_config_source_intervals_and_reference(mod, tmp_path):
    path=write_source(tmp_path/'x'); root=tmp_path/'cache'; cfg=config(mod)
    ref=np.arange(1000,1400,100,dtype=np.int64)
    build=lambda c=cfg,r=ref,ints=[]: mod.build_ppg_cache(path,ints,root,c,r).cache_key
    keys=[build(),build(replace(cfg,max_gap_ms=300)),build(replace(cfg,max_rows=2)),build(replace(cfg,chunksize=2)),build(replace(cfg,positive_overlap=.5)),build(replace(cfg,window_sec=.3)),build(replace(cfg,schema_version=2)),build(r=ref+100),build(r=ref[:-1]),build(ints=[(1000,1200)])]
    path.write_text(path.read_text()+'\n')
    keys.append(build())
    assert len(set(keys))==len(keys)


def test_compact_threshold_is_keyed_without_an_explicit_reference(mod, tmp_path):
    path = write_source(tmp_path / 'x')
    root = tmp_path / 'cache'
    dense = mod.build_ppg_cache(
        path, [], root, config(mod, max_dense_samples=10), lazy=True
    )
    compact = mod.build_ppg_cache(
        path, [], root, config(mod, max_dense_samples=2), lazy=True
    )

    assert dense.cache_hit is False
    assert compact.cache_hit is False
    assert compact.cache_key != dense.cache_key
    assert compact.metadata['storage'] == 'all_missing_compact'
    assert compact.features_loaded is False


@pytest.mark.parametrize('failure', ['save', 'rename', 'interrupt'])
def test_atomic_failures_leave_no_partial_cache_and_resume(mod,tmp_path,monkeypatch,failure):
    path=write_source(tmp_path/'x'); root=tmp_path/'cache'
    import eating_detection.cache as storage
    error=KeyboardInterrupt if failure=='interrupt' else OSError
    def fail(*a,**kw): raise error('simulated failure')
    with monkeypatch.context() as patch:
        patch.setattr(storage.np if failure=='save' else storage.os, 'savez' if failure=='save' else 'replace', fail)
        with pytest.raises(error): mod.build_ppg_cache(path,[],root,config(mod))
    assert not list(root.rglob('*.npz')) and not list(root.rglob('*.tmp-*'))
    assert not mod.build_ppg_cache(path,[],root,config(mod)).cache_hit
    assert mod.build_ppg_cache(path,[],root,config(mod)).cache_hit


def test_completed_file_survives_interrupted_sequence(mod,tmp_path,monkeypatch):
    first=write_source(tmp_path/'a'); second=write_source(tmp_path/'b')
    root=tmp_path/'cache'
    mod.build_ppg_cache(first,[],root,config(mod))
    with monkeypatch.context() as patch:
        def fail(*a,**kw): raise KeyboardInterrupt()
        patch.setattr(mod,'iter_ppg_chunks',fail)
        with pytest.raises(KeyboardInterrupt): mod.build_ppg_cache(second,[],root,config(mod))
    assert mod.build_ppg_cache(first,[],root,config(mod)).cache_hit
    assert not mod.build_ppg_cache(second,[],root,config(mod)).cache_hit


def test_no_coverage_requires_reference_and_bounds_respected(mod,tmp_path):
    path=write_source(tmp_path/'x', [0,0])
    with pytest.raises(ValueError,match='reference|coverage'):
        mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod))
    path=write_source(tmp_path/'y')
    cache=mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod,max_rows=2,chunksize=1))
    assert cache.timestamps_ms[-1] <= 1100
    assert np.all(cache.window_indices[:,1] <= cache.features.shape[1])


def test_reference_validation_and_fixed_preprocessing(mod,tmp_path):
    with pytest.raises(ValueError): mod.PPGCacheConfig(preprocess_variant='standardized')
    path=write_source(tmp_path/'x')
    for ref in ([1000,999],[1000,1111],[1000.5,1100.5]):
        with pytest.raises(ValueError): mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod),ref)


def test_optional_constant_stream_quality_policy_is_keyed(mod,tmp_path):
    path=write_source(tmp_path/'x')
    base=mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod))
    kept=config(mod,flat_policy='keep')
    flat=mod.build_ppg_cache(path,[],tmp_path/'cache',kept)
    assert not base.quality_mask.any() and flat.quality_mask.any()
    assert not base.features.any() and flat.cache_key != base.cache_key
    values=np.full((4,44),2.)
    values[-1,0]=3
    varying=write_source(tmp_path/'varying',values=values)
    assert mod.build_ppg_cache(varying,[],tmp_path/'cache',config(mod)).quality_mask.all()


def test_downsampling_masks_outputs_influenced_by_invalid_rows(mod,tmp_path):
    times=np.arange(1000,2001,10)
    clean_values=np.ones((len(times),44))
    damaged_values=clean_values.copy()
    damaged_values[times==1500]=np.inf
    reference=np.arange(1000,2001,40,dtype=np.int64)
    cache_config=mod.PPGCacheConfig(
        resample_hz=25,max_gap_ms=100,window_sec=.2,step_sec=.1,flat_policy='keep',
    )
    clean=mod.build_ppg_cache(
        write_source(tmp_path/'clean',times,clean_values),[],tmp_path/'cache',
        cache_config,reference,
    )
    damaged=mod.build_ppg_cache(
        write_source(tmp_path/'damaged',times,damaged_values),[],tmp_path/'cache',
        cache_config,reference,
    )
    changed=~np.isclose(damaged.features[0],clean.features[0],atol=1e-6)
    assert changed.any()
    assert not damaged.quality_mask[0,changed].any()
    assert not damaged.features[:44,changed].any()
    assert damaged.quality_mask[0,0]


def test_invalid_duplicate_rejects_timestamp_without_contaminating_neighbors(mod,tmp_path):
    values=np.full((5,44),2.)
    values[2]=np.inf
    path=write_source(tmp_path/'x',[1000,1100,1100,1200,1300],values)
    cache=mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod,flat_policy='keep'))
    np.testing.assert_array_equal(cache.quality_mask[0],[True,False,True,True])
    np.testing.assert_allclose(cache.features[:44,[0,2,3]],2)


def test_fixed_constant_detrend_is_keyed_and_excludes_invalid_rows(mod,tmp_path):
    values=np.tile([2.,0.,4.,6.],(44,1)).T
    path=write_source(tmp_path/'x',values=values)
    raw=mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod))
    detrended=mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod,preprocess_variant='constant_detrend_mask'))
    np.testing.assert_allclose(detrended.features[:44],np.tile([-2.,0.,0.,2.],(44,1)))
    np.testing.assert_array_equal(detrended.quality_mask,raw.quality_mask)
    assert detrended.cache_key != raw.cache_key


@pytest.mark.parametrize('lazy',[False,True])
def test_cache_hit_reports_elapsed_time(mod,tmp_path,monkeypatch,lazy):
    path=write_source(tmp_path/'x')
    mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod))
    ticks=iter([10.,12.])
    monkeypatch.setattr(mod.time,'perf_counter',lambda:next(ticks))
    cache=mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod),lazy=lazy)
    assert cache.timings['cache_load_sec']==2.


def test_zero_byte_source_retains_reference(mod,tmp_path):
    path=tmp_path/'empty'; path.write_text('')
    cache=mod.build_ppg_cache(path,[],tmp_path/'cache',config(mod),np.arange(1000,1400,100))
    assert cache.features.shape==(45,4) and not cache.features.any()


def test_additional_cache_key_inputs(mod,tmp_path):
    import os
    path=write_source(tmp_path/'x'); root=tmp_path/'cache'; cfg=config(mod)
    base=mod.build_ppg_cache(path,[],root,cfg)
    keys=[base.cache_key]
    for change in ({'resample_hz':25},{'step_sec':.2},{'boundary_mode':'ignore'}):
        keys.append(mod.build_ppg_cache(path,[],root,replace(cfg,**change)).cache_key)
    other=tmp_path/'other';other.write_bytes(path.read_bytes())
    keys.append(mod.build_ppg_cache(other,[],root,cfg).cache_key)
    stat=path.stat();os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000_000))
    keys.append(mod.build_ppg_cache(path,[],root,cfg).cache_key)
    assert len(set(keys))==len(keys)

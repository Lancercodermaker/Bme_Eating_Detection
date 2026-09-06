"""Independent raw PPG caches; normalization belongs to training folds.

Row quality requires all 44 finite channels and a nonzero row. By default,
reject_constant_stream rejects a whole stream only when at least two valid
canonical rows are exactly constant in every channel; no amplitude threshold
is inferred. The explicit keep policy preserves nonzero constant signals.
Any invalid duplicate makes its timestamp invalid, and invalid timestamps remain
interpolation barriers. Invalid values are zeroed before the anti-alias filter.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .cache import (
    FeatureCache, LazyFeatureCache, _from_arrays, _load_cache, _load_lazy_cache,
    _participant_from_path, _source_metadata, _write_cache,
)
from .io import iter_ppg_chunks
from .labels import label_window
from .preprocess import resample_uniform
from .timebase import CanonicalStream, infer_rate_hz, interpolate_uniform


@dataclass(frozen=True)
class PPGCacheConfig:
    resample_hz: int = 25
    max_gap_ms: int = 2000
    preprocess_variant: str = 'raw_mask'
    window_sec: float = 15.
    step_sec: float = 3.
    positive_overlap: float = .25
    boundary_mode: str = 'soft'
    chunksize: int = 50_000
    max_rows: int | None = None
    waveform_channels: int = 44
    quality_channels: int = 1
    schema_version: int = 1
    flat_policy: str = 'reject_constant_stream'

    def __post_init__(self):
        if self.resample_hz <= 0 or self.max_gap_ms < 0:
            raise ValueError('invalid sampling rate or gap')
        if not 0 < self.step_sec <= self.window_sec:
            raise ValueError('step must be positive and no larger than window')
        if not 0 <= self.positive_overlap <= 1 or self.boundary_mode not in {'soft', 'ignore'}:
            raise ValueError('invalid label configuration')
        if self.chunksize <= 0 or (self.max_rows is not None and self.max_rows <= 0):
            raise ValueError('row limits must be positive')
        if self.preprocess_variant not in {'raw_mask', 'constant_detrend_mask'}:
            raise ValueError('unknown fixed PPG preprocessing variant')
        if self.flat_policy not in {'keep', 'reject_constant_stream'}:
            raise ValueError('unknown flat signal policy')
        if self.waveform_channels != 44 or self.quality_channels != 1 or self.schema_version < 1:
            raise ValueError('PPG requires 44 waveform and one quality channel, with positive schema')

    def as_dict(self):
        return asdict(self)


def _reference_grid(reference, rate):
    if reference is None:
        return None
    original = np.asarray(reference)
    if original.ndim != 1 or not np.isfinite(original).all():
        raise ValueError('reference must be a finite one-dimensional grid')
    grid = original.astype(np.int64)
    if not np.array_equal(grid, original):
        raise ValueError('reference timestamps must be integral milliseconds')
    if len(grid):
        expected = np.rint(grid[0] + np.arange(len(grid)) * 1000. / rate).astype(np.int64)
        if not np.array_equal(grid, expected) or np.any(np.diff(grid) <= 0):
            raise ValueError('reference must match the configured uniform sampling grid')
    return np.ascontiguousarray(grid)


def _canonical_rows(path, config):
    times, values, valid = [], [], []
    if path.stat().st_size == 0:
        return np.empty(0, np.int64), np.empty((0,44), np.float32), np.empty(0,bool)
    for chunk in iter_ppg_chunks(path, chunksize=config.chunksize, max_rows=config.max_rows):
        times.append(chunk.timestamps_ms)
        values.append(chunk.values)
        valid.append(chunk.valid)
    if not times:
        return np.empty(0, np.int64), np.empty((0,44), np.float32), np.empty(0,bool)
    ts, x, good = np.concatenate(times), np.concatenate(values), np.concatenate(valid)
    keep = ts > 0
    ts, x, good = ts[keep], x[keep], good[keep]
    good &= np.isfinite(x).all(axis=1) & np.any(x != 0, axis=1)
    order = np.argsort(ts, kind='stable')
    ts, x, good = ts[order], x[order], good[order]
    unique, starts, counts = np.unique(ts, return_index=True, return_counts=True)
    if not len(unique):
        return unique, np.empty((0,44), np.float32), good
    quality = np.logical_and.reduceat(good, starts)
    clean = np.where(good[:,None], x, 0).astype(np.float64)
    averaged = np.add.reduceat(clean, starts, axis=0) / counts[:,None]
    averaged[~quality] = 0
    observed = averaged[quality]
    if (config.flat_policy == 'reject_constant_stream' and len(observed) >= 2
            and np.all(observed == observed[0])):
        quality[:] = False
        averaged[:] = 0
    return unique, averaged.astype(np.float32), quality


def _quality_at(grid, ts, quality, max_gap):
    if not len(ts):
        return np.zeros(len(grid),bool)
    right = np.searchsorted(ts, grid, side='left').clip(0,len(ts)-1)
    left = (right-1).clip(0,len(ts)-1)
    exact = ts[right] == grid
    left = np.where(exact,right,left)
    return ((grid >= ts[0]) & (grid <= ts[-1]) & quality[left] & quality[right]
            & ((ts[right]-ts[left]) <= max_gap))


def _build_arrays(path, intervals, config, reference):
    ts, values, quality = _canonical_rows(path,config)
    if config.preprocess_variant == 'constant_detrend_mask' and quality.any():
        # Fixed per-file DC removal, not a fitted cross-file standardizer.
        values[quality] -= values[quality].mean(axis=0,dtype=np.float64).astype(np.float32)
    if reference is None:
        if not len(ts):
            raise ValueError('no positive PPG timestamp coverage; supply reference timestamps')
        length = int(np.floor((ts[-1]-ts[0])*config.resample_hz/1000.))+1
        reference = np.rint(ts[0]+np.arange(length)*1000./config.resample_hz).astype(np.int64)
    length = len(reference)
    waveform = np.zeros((length,44),np.float32)
    output_quality = _quality_at(reference, ts, quality, config.max_gap_ms)
    if length and len(ts) and quality.any():
        source_hz = infer_rate_hz(ts) if len(ts)>1 else config.resample_hz
        grid, uniform, _ = interpolate_uniform(
            CanonicalStream(ts, values, 0), source_hz, int(reference[0]),
            int(reference[-1]), config.max_gap_ms,
        )
        # Use unrounded coordinates for quality; interpolate_uniform returns truncated ms.
        uniform_times = reference[0] + np.arange(len(grid))*1000./source_hz
        uniform_quality = _quality_at(uniform_times,ts,quality,config.max_gap_ms)
        uniform[~uniform_quality] = 0
        sampled = resample_uniform(uniform,source_hz,config.resample_hz)
        # Resampling is a filter, so a zeroed invalid row can otherwise alter
        # adjacent samples that the pointwise reference-grid check considers
        # valid. Compare the resampled availability signal with all-valid
        # support and turn every affected output into an explicit barrier.
        sampled_quality = resample_uniform(
            uniform_quality.astype(np.float32)[:,None],source_hz,config.resample_hz,
        )[:,0]
        sampled_support = resample_uniform(
            np.ones((len(uniform_quality),1),np.float32),source_hz,config.resample_hz,
        )[:,0]
        filtered_quality = np.isclose(
            sampled_quality,sampled_support,rtol=0.,atol=1e-6,
        )
        take = min(length,len(sampled),len(filtered_quality))
        waveform[:take] = sampled[:take]
        output_quality[:take] &= filtered_quality[:take]
        output_quality[take:] = False
    waveform[~output_quality] = 0
    window = max(1,int(round(config.window_sec*config.resample_hz)))
    step = max(1,int(round(config.step_sec*config.resample_hz)))
    offsets = np.arange(0,max(0,length-window+1),step,dtype=np.int64)
    starts = reference[offsets]
    ends = np.rint(starts+window*1000./config.resample_hz).astype(np.int64)
    labels = [label_window((int(s),int(e)),intervals,config.positive_overlap,config.boundary_mode) for s,e in zip(starts,ends)]
    return {
        'timestamps_ms': reference.copy(),
        'features': np.ascontiguousarray(np.vstack([waveform.T,output_quality[None,:]]),dtype=np.float32),
        'quality_mask': np.ascontiguousarray(output_quality[None,:]),
        'window_indices': np.column_stack([offsets,offsets+window]).astype(np.int64),
        'window_starts_ms': starts, 'window_ends_ms': ends,
        'window_labels': np.asarray([0 if x is None else x for x in labels],np.float32),
        'window_loss_mask': np.asarray([x is not None for x in labels],bool),
    }


def build_ppg_cache(source_path, intervals, cache_root, config,
                    reference_timestamps_ms=None, lazy=False) -> FeatureCache | LazyFeatureCache:
    """Build one atomic file; repeating a sequence resumes completed files.

    Explicit reference grids preserve every M0 sample and window, including
    observations outside PPG coverage (zero waveform with false quality).
    Lazy objects follow FeatureCache's contract: timestamps_ms is None on load.
    """
    source_path = Path(source_path)
    reference = _reference_grid(reference_timestamps_ms,config.resample_hz)
    reference_metadata = None if reference is None else {
        'sha256': hashlib.sha256(reference.astype('<i8').tobytes()).hexdigest(),
        'start_ms': int(reference[0]) if len(reference) else None,
        'length': len(reference),
    }
    payload = {'modality':'ppg','source':_source_metadata(source_path),
               'config':config.as_dict(),'intervals':[list(i) for i in sorted(intervals)],
               'reference':reference_metadata}
    key = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    location = Path(cache_root)/'ppg'/key[:2]/f'{key}.npz'
    started = time.perf_counter()
    if location.exists():
        cached = (_load_lazy_cache if lazy else _load_cache)(location,key,source_path)
        return replace(cached,timings={'cache_load_sec':time.perf_counter()-started})
    arrays = _build_arrays(source_path,intervals,config,reference)
    participant = _participant_from_path(source_path)
    metadata = {**payload,'cache_key':key,'participant':participant,
                'array_shapes':{n:list(v.shape) for n,v in arrays.items()},
                'build_time_sec':time.perf_counter()-started}
    _write_cache(location,metadata,arrays)
    timings = {'build_sec':time.perf_counter()-started}
    if lazy:
        return _load_lazy_cache(location,key,source_path,cache_hit=False,timings=timings)
    return _from_arrays(location,key,source_path,participant,arrays,metadata,False,timings)

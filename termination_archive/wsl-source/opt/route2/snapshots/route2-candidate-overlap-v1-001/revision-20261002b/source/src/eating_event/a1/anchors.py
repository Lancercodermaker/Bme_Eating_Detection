"""Approved input identities, independent of declarations in the input files."""
from pathlib import Path
from .execution import sha

LEDGER = '6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d'
INPUTS = {
    'cache_manifest': ('artifacts/g1-candidate-coverage-v4/cache-manifest.json', 'dbcb03c4fa2e26baf4d0e0d7d9127eafc85bfca46a3e80cae0a7b5c0fba0bd3c'),
    'manifest_audit': ('artifacts/g1-candidate-coverage-v4/manifest-audit.json', 'f8682c8632b78c29ea3cc78b13e81b3e40b5e8c8c1fd48b6253a68baff34ffb8'),
    'eligibility': ('artifacts/g1-candidate-coverage-v4/eligibility.json', '68c5cd8ec6fe12813f8b39c9d31000d4e18bd6ea732840b67428db643aef3a30'),
    'fold_manifest': ('artifacts/g1-event-balanced-candidate-objective-probe-v1/fold-manifest.json', 'bce57f5cc41be47b1327ded5b85c6d94b9007fccfacd706fd784b78a3a722912'),
    'models_manifest': ('artifacts/g1-event-balanced-candidate-objective-probe-v1/models-manifest.json', '3d4c2bb47c23d5a587c53d71c08e2514ad830b97c45f98130ef1cb225c2c9fe3'),
}


def verify_inputs(root, config):
    if config.d3_revision != 'D3-Ready-v1':
        raise ValueError('approved D3 revision required')
    for key,(relative,expected) in INPUTS.items():
        path=Path(root)/relative
        if config.paths.get(key) != relative or not path.is_file() or sha(path) != expected:
            raise ValueError(f'approved input hash/path mismatch: {key}')
    if config.paths.get('cache_root') != 'artifacts/g1-formal-cache-v3-final':
        raise ValueError('unapproved cache root')


def verify_bundle(bundle):
    if bundle.source_hashes['eligibility_declared_denominator'] != LEDGER:
        raise ValueError('approved ledger hash mismatch')
    if (len(bundle.manifest_entries),len(bundle.participants),len(bundle.windows),sum(map(len,bundle.truths.values()))) != (1127,41,632100,234):
        raise ValueError('approved population mismatch')
    if len(bundle.label_changes) != 196 or any((r['old_label'],r['new_label']) != (0,-1) for r in bundle.label_changes):
        raise ValueError('D3 approved label delta mismatch')
    if sum(r['outside_windows'] for r in bundle.identity_audit) != 965:
        raise ValueError('D3 boundary audit mismatch')

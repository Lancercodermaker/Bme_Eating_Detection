"""Runtime provenance helpers for formal candidate-cache consumers."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from eating_event.coverage import cache_manifest_sha256


FORMAL_CACHE_DIR_NAME = "g1-formal-cache-v3-final"


def resolve_formal_cache_dir(path: str | Path) -> Path:
    """Resolve and enforce the approved formal cache root."""

    resolved = Path(path).expanduser().resolve()
    if resolved.name != FORMAL_CACHE_DIR_NAME:
        raise ValueError(
            f"formal G1/E2E requires cache root named {FORMAL_CACHE_DIR_NAME!r}; "
            f"received {resolved}"
        )
    return resolved


def build_cache_runtime_provenance(
    cache_root: str | Path,
    entries: Sequence[Mapping[str, object]],
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Return bounded, identity-bearing provenance for loaded cache entries."""

    resolved = resolve_formal_cache_dir(cache_root)
    rows = [dict(entry) for entry in entries]
    required_metadata = (
        "eligibility_contract_version",
        "eligibility_contract_hash",
        "eligibility_artifact_sha256",
        "label_contract_version",
        "label_contract_hash",
        "window_seconds",
        "step_seconds",
    )
    missing = [key for key in required_metadata if key not in metadata]
    if missing:
        raise ValueError(f"cache provenance metadata missing {', '.join(missing)}")
    return {
        "resolved_cache_path": str(resolved),
        "cache_entry_count": len(rows),
        "cache_manifest_sha256": cache_manifest_sha256(rows),
        "eligibility_contract_version": metadata["eligibility_contract_version"],
        "eligibility_contract_hash": metadata["eligibility_contract_hash"],
        "eligibility_artifact_sha256": metadata["eligibility_artifact_sha256"],
        "label_contract_version": metadata["label_contract_version"],
        "label_contract_hash": metadata["label_contract_hash"],
        "window_seconds": metadata["window_seconds"],
        "step_seconds": metadata["step_seconds"],
    }

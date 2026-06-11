"""Config validation for the MELD + PET pipeline."""
from __future__ import annotations

import os
from typing import Any

REQUIRED_KEYS = (
    "project_root",
    "pipeline_dir",
    "data_dir",
    "work",
    "mapping",
    "samples",
    "bids_root",
    "petprep_out",
    "petprep_sif",
    "sif",
    "fs_license",
    "meld_license",
    "models_src",
    "meld_params_src",
    "apptainer_bin",
    "tracer_mode",
    "abnormal_z",
    "asym_concordance_pct",
    "dice_concordance",
)


def validate_config(cfg: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_KEYS:
        if key not in cfg:
            errors.append(f"missing required key: {key}")

    for key in ("sif", "petprep_sif", "fs_license", "meld_license", "mapping"):
        path = cfg.get(key)
        if path and not os.path.isfile(path):
            errors.append(f"{key} not found: {path}")

    for key in ("bids_root", "models_src", "meld_params_src"):
        path = cfg.get(key)
        if path and not os.path.isdir(path):
            errors.append(f"{key} not a directory: {path}")

    resolution = cfg.get("resolution_csv")
    if resolution and not os.path.isfile(resolution):
        warnings.append(f"resolution_csv not found (optional): {resolution}")

    work = cfg.get("work")
    if work:
        if os.path.exists(work) and not os.access(work, os.W_OK):
            errors.append(f"work not writable: {work}")
        elif not os.path.exists(work):
            try:
                os.makedirs(work, exist_ok=True)
            except OSError as exc:
                errors.append(f"cannot create work dir {work}: {exc}")

    petprep_out = cfg.get("petprep_out")
    if petprep_out and not os.path.isdir(petprep_out):
        try:
            os.makedirs(petprep_out, exist_ok=True)
        except OSError as exc:
            warnings.append(f"cannot create petprep_out {petprep_out}: {exc}")

    samples = cfg.get("samples")
    if samples and not os.path.isfile(samples):
        warnings.append(f"samples.tsv missing — run `meldpet samples`: {samples}")

    mode = cfg.get("tracer_mode")
    if mode and mode not in ("deficit", "excess"):
        errors.append(f"tracer_mode must be 'deficit' or 'excess', got {mode!r}")

    for key in ("abnormal_z", "asym_concordance_pct", "dice_concordance"):
        val = cfg.get(key)
        if val is not None:
            try:
                float(val)
            except (TypeError, ValueError):
                errors.append(f"{key} must be numeric, got {val!r}")

    return errors, warnings

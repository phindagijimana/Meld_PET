# MELD + PET — User Guide

## Pipeline overview

```
BIDS (PET + T1w)
    │
prepare ──► MELD input (T1w ± FLAIR)
    │
    ├── petprep ──► PETPrep ──► work/pet/<sub>_pet.nii.gz
    │
    └── meld ─────► prediction.nii.gz + T1.mgz + aparc+aseg.mgz
              │
              ▼
         register ──► pet_in_meld.nii.gz + pet_in_clusters_<sub>.csv
              │
              ▼
         visualize ──► PNG overlays
              │
              ▼
         aggregate ──► pet_cohort_stats.csv
```

### Why this works

MELD writes `prediction.nii.gz` in FreeSurfer conformed T1 space (same grid as `T1.mgz`). PETPrep produces a PET reference in T1w space; a **second rigid registration** (`mri_coreg` + `mri_vol2vol`) aligns that PET to MELD's `T1.mgz`. Asymmetry and concordance stats are then computed with nibabel/numpy on the shared grid — the same design as Meld_CBF.

MELD and PETPrep run **independently** after `prepare` and can execute in parallel on SLURM.

## Prerequisites

1. **BIDS dataset** with PET and T1w per subject (`bids_root`).
2. **PETPrep SIF** — `apptainer build petprep.sif docker://ghcr.io/nipreps/petprep:0.0.6`
3. **MELD SIF** + licenses + models + meld_params (shared institutional install).
4. **Mapping CSV** — `EP_ID,BIDS_ID` columns (see `PET_BIDS_SUB.csv.example`).

Optional: session resolution CSV (`resolution_csv`) with columns `BIDS_ID,resolved_session` when PET and structural sessions differ (same pattern as Meld_CBF).

## Statistics (`pet_stats.py`)

Computed in the **register** stage after `pet_in_meld.nii.gz` exists.

| Metric | Columns | Meaning |
|--------|---------|---------|
| ROI asymmetry | `ipsi_roi_pet`, `contra_roi_pet`, `roi_asym_pct` | Host ROI vs homologue |
| Cluster mirror AI | `cluster_mirror_ipsi_pet`, `cluster_mirror_contra_pet`, `cluster_mirror_ai` | Lesion vs L↔R-flipped mask |
| GM z-score | `gm_z` | Cluster mean vs cortical GM |
| Spatial concordance | `frac_abnormal`, `dice_abnormal` | Overlap with tracer-abnormal GM |

**Tracer modes** (`config.yaml` → `tracer_mode`):

- `deficit` — lower uptake abnormal (FDG hypometabolism); negative asymmetry = ipsilateral deficit
- `excess` — higher uptake abnormal; positive asymmetry = ipsilateral excess

Cohort concordance (`meldpet aggregate`):

| Column | Meaning |
|--------|---------|
| `tracer_concordant` | ROI asymmetry matches tracer direction |
| `spatial_concordant` | `dice_abnormal` ≥ threshold |
| `concordance_call` | `concordant` / `partial` / `discordant` |

Relationship: `roi_asym_pct ≈ 200 × cluster_mirror_ai` when comparing the same pair.

## PETPrep derivative path

After PETPrep, the workflow locates the T1w-space PET reference using `petprep_ref_glob` in config (default):

```
{sub}/{session}/pet/{sub}_{session}_space-*T1w*desc-*pet*.nii.gz
```

Adjust the glob if your PETPrep version uses different filenames. The resolved file is copied to `work/pet/<sub>_pet.nii.gz`.

## Resource hints

| Rule | Default SLURM | Notes |
|------|---------------|-------|
| petprep | 32G, 4 CPU, 8h | ~24GB image; per-subject work dir under `work/petprep_work/` |
| meld | 64G, 8 CPU, 24h | FreeSurfer recon dominates |
| register | 16G, 2 CPU, 2h | Fast after MELD + PETPrep |
| visualize | 8G, 1 CPU, 30m | Headless PNGs |

## Repository layout

```
pipeline/
├── meldpet/cli.py              CLI wrapper
├── config/config.example.yaml
├── workflow/Snakefile + rules/
├── pet_register_in_container.sh
├── pet_stats.py
├── pet_visualize.py
└── profiles/slurm/
```

Outputs live under `work/` (bound to `/data` in the MELD container). PETPrep reads `bids_root` and writes to `petprep_out`.

# MELD + PET — User Guide

Detailed reference for the pipeline. For install and a quick start, see [README.md](../README.md).

## Pipeline overview

```
BIDS (PET + T1w)
    │
prepare ──► MELD input (T1w only; set `meld_t1_only: false` to include FLAIR)
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

MELD writes `prediction.nii.gz` in FreeSurfer conformed T1 space (same grid as `T1.mgz`). PETPrep produces a PET reference in T1w space; a **second rigid registration** (`mri_coreg` + `mri_vol2vol`) aligns that PET to MELD's `T1.mgz`. Asymmetry and concordance stats are computed with nibabel/numpy on the shared grid — the same design as Meld_CBF.

MELD and PETPrep run **independently** after `prepare` and can execute in parallel on SLURM.

## Prerequisites

1. **BIDS dataset** with PET and T1w per subject (`bids_root` in config).
2. **PETPrep SIF** — built once on your cluster:

   ```bash
   apptainer build petprep.sif docker://ghcr.io/nipreps/petprep:0.0.6
   ```

3. **MELD SIF** + FreeSurfer/MELD licenses + `models/` + `meld_params/` (shared institutional install):

   ```bash
   apptainer build meld_graph_v2.2.4.sif docker://meldproject/meld_graph:v2.2.4
   ```

4. **Mapping CSV** — `EP_ID,BIDS_ID` columns (see `PET_BIDS_SUB.csv.example` at repo root).

Optional: `resolution_csv` with columns `BIDS_ID,resolved_session` when PET and structural sessions differ (same pattern as Meld_CBF).

## Setup notes

- **BIDS first** — PET must be in BIDS before PETPrep.
- **Session pairing** — use the T1w from the same session as the PET when possible; encode this in `samples.tsv` via `meldpet samples`.
- **Tracer mode** — set `tracer_mode: deficit` (e.g. FDG hypometabolism) or `excess` in `config.yaml`.
- **Independent runs** — MELD and PETPrep run in parallel after `prepare`; fusion happens in `register`.

## CLI reference

```bash
meldpet check                    # validate image / licenses / paths / runtime
meldpet samples                  # (re)build config/samples.tsv

meldpet run sub-002              # one subject, end-to-end (MELD recon is slow)
meldpet run --aggregate sub-002  # through cohort roll-up
meldpet run --profile slurm -j 16

meldpet prepare sub-002          # stage only
meldpet petprep sub-002
meldpet meld sub-002
meldpet register sub-002
meldpet visualize sub-002
meldpet aggregate

meldpet status
meldpet dag -o dag.svg
meldpet -n all                   # dry-run the full DAG
```

Stage subcommands accept any subset of subjects, or none for the full cohort. Everything is config-driven via `config/config.yaml`.

## Configuration

Copy `config/config.example.yaml` to `config/config.yaml` and edit:

| Key | Purpose |
|-----|---------|
| `bids_root` | BIDS dataset with PET + T1w |
| `petprep_sif`, `sif` | Apptainer images |
| `fs_license`, `meld_license` | License files |
| `models_src`, `meld_params_src` | Shared MELD assets |
| `mapping` | EP_ID ↔ BIDS_ID CSV |
| `petprep_out` | PETPrep derivatives root |
| `petprep_ref_glob` | Glob to locate T1w-space PET after PETPrep |
| `tracer_mode` | `deficit` or `excess` |
| `abnormal_z` | Voxelwise z threshold for spatial concordance |
| `asym_concordance_pct`, `dice_concordance` | Cohort concordance thresholds |
| `work` | Pipeline outputs (bound to `/data` in MELD container) |

Default PETPrep derivative glob:

```
{sub}/{session}/pet/{sub}_{session}_space-*T1w*desc-*pet*.nii.gz
```

The matched file is copied to `work/pet/<sub>_pet.nii.gz`.

## SLURM

```bash
meldpet run --profile slurm -j 10
```

Profile: `profiles/slurm/config.yaml`. Resource hints (override in config or profile):

| Rule | Default | Notes |
|------|---------|-------|
| petprep | 32G, 4 CPU, 8h | ~24GB image |
| meld | 64G, 8 CPU, 24h | FreeSurfer recon dominates |
| register | 16G, 2 CPU, 2h | After MELD + PETPrep |
| visualize | 8G, 1 CPU, 30m | Headless PNGs |

## Asymmetry analysis

Asymmetry is computed in the **register** stage, after PET is resampled to the MELD/FreeSurfer T1 grid. Registration uses FreeSurfer `mri_coreg` + `mri_vol2vol`; nibabel/numpy are used only in `pet_stats.py`.

**Inputs (same grid):**

- `pet_in_meld.nii.gz` — PET resampled to `T1.mgz` space
- `prediction.nii.gz` — MELD lesion mask
- `aparc+aseg.mgz` — FreeSurfer parcellation (ROI method only)

**Output:** `work/output/pet_aligned/<sub>/pet_in_clusters_<sub>.csv`

### ROI asymmetry — `roi_asym_pct`

Compares mean PET in the anatomical ROI hosting the lesion vs its FreeSurfer homologue (label ± 1000).

Formula: `(ipsi − contra) / mean(ipsi, contra) × 100`. Negative ⇒ ipsilateral deficit (for deficit tracers).

Also reported: `cluster_vs_contra_pct` (cluster mean vs contralateral ROI).

### Cluster mirror asymmetry — `cluster_mirror_ai`

Compares mean PET inside the lesion mask vs mean PET under the **L↔R-flipped** mask on the same `pet_in_meld.nii.gz` (homotopic mirror, not parcellation-based).

Formula: `(ipsi − contra) / (ipsi + contra)`, range ~[−1, +1].

| Column | Meaning |
|--------|---------|
| `cluster_mirror_ipsi_pet` | Mean PET in lesion (= `pet_mean`) |
| `cluster_mirror_contra_pet` | Mean PET in mirror region |
| `cluster_mirror_ai` | Normalized asymmetry index |

Computed for `all_clusters` and each `cluster_N`. Relationship: `roi_asym_pct ≈ 200 × cluster_mirror_ai` when the same pair uses the two denominators.

**Mask flip (in memory only):** the lesion mask is flipped with `np.flip(mask, axis=lr_axis)` where `lr_axis` is derived from the image affine (RAS x direction). The PET array is not flipped.

### Other metrics

| Metric | Columns | Meaning |
|--------|---------|---------|
| GM z-score | `gm_z` | Cluster mean vs subject's cortical GM |
| Spatial concordance | `frac_abnormal`, `dice_abnormal` | Overlap with tracer-abnormal GM voxels |

If MELD finds no lesion, the CSV has `cluster=none` and asymmetry columns are empty.

## Cohort concordance (`meldpet aggregate`)

Applied on the `all_clusters` row (and echoed per row in the cohort table):

| Column | Meaning |
|--------|---------|
| `tracer_concordant` | ROI asymmetry matches tracer direction |
| `spatial_concordant` | `dice_abnormal` ≥ threshold |
| `concordance_call` | `concordant` / `partial` / `discordant` |

For `tracer_mode: deficit`, `tracer_concordant` when `roi_asym_pct ≤ asym_concordance_pct` (default −8%).

## Repository layout

```
pipeline/
├── meldpet/cli.py              `meldpet` console script
├── config/config.example.yaml
├── workflow/Snakefile + rules/
├── pet_register_in_container.sh
├── pet_stats.py
├── pet_visualize.py
└── profiles/slurm/
```

Outputs live under `work/`. PETPrep reads `bids_root` and writes to `petprep_out`.

## Architecture

Snakemake orchestrates the DAG (resumability, SLURM, provenance). Neuroimaging runs in the **MELD apptainer image** (FreeSurfer, `mri_coreg`, stats scripts) and the **PETPrep apptainer image** (BIDS App). The host only needs Snakemake and the `meldpet` Python package.

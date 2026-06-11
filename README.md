# MELD + PET pipeline

Runs **MELD Graph** lesion prediction on T1w, **PETPrep** preprocessing on BIDS PET+T1w, registers PET into MELD space, and computes tracer-aware asymmetry and concordance statistics with cohort roll-up.

Orchestrated by **Snakemake** and driven by the **`meldpet` CLI**.

## Install

```bash
cd Meld_PET/pipeline
conda env create -f workflow/envs/meldpet.yaml && conda activate meldpet
pip install -e .
```

Copy and edit config:

```bash
cp config/config.example.yaml config/config.yaml
# edit paths: bids_root, meld sif/licenses, petprep_sif, mapping CSV
```

Build PETPrep and MELD container images on your cluster (once):

```bash
apptainer build petprep.sif docker://ghcr.io/nipreps/petprep:0.0.6
apptainer build meld_graph_v2.2.4.sif docker://meldproject/meld_graph:v2.2.4
```

## Quick start

```bash
meldpet check
meldpet samples

meldpet run sub-002              # one subject, end-to-end
meldpet run --profile slurm      # whole cohort on SLURM
meldpet aggregate                # cohort stats + concordance
meldpet status
```

## Pipeline stages

```
BIDS (PET + T1w)
    │
    ├─ prepare ──► MELD input T1w/FLAIR
    │
    ├─ petprep ──► PETPrep derivatives ──► work/pet/<sub>_pet.nii.gz
    │
    └─ meld ─────► prediction.nii.gz + T1.mgz + aparc+aseg.mgz
              │
              ▼
         register (mri_coreg → pet_in_meld.nii.gz → pet_stats.py)
              │
              ▼
         visualize → aggregate
```

## Key outputs (`work/output/`)

| Path | Description |
|------|-------------|
| `pet_aligned/<sub>/pet_in_meld.nii.gz` | PET on MELD prediction grid |
| `pet_aligned/<sub>/pet_in_clusters_<sub>.csv` | Per-cluster asymmetry + concordance |
| `pet_aligned/<sub>/figures/*.png` | T1 / PET / prediction overlays |
| `pet_cohort_stats.csv` | Cohort table after `meldpet aggregate` |

## Docs

- [pipeline/README.md](pipeline/README.md) — CLI quick reference
- [pipeline/USER_GUIDE.md](pipeline/USER_GUIDE.md) — statistics dictionary, config, SLURM
- [meld.md](meld.md) — MELD container implementation
- [petprep.md](petprep.md) — PETPrep container implementation

## Notes

- **BIDS first**: PET must be in BIDS before PETPrep (`bids_root` in config).
- **Independent runs**: MELD and PETPrep run in parallel after `prepare`; fusion happens in `register`.
- **Tracer mode**: set `tracer_mode: deficit` (FDG) or `excess` in `config.yaml`.
- Patient data and paths are not committed — see `.gitignore`.

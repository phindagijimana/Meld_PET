# meldpet — MELD + PET Pipeline Documentation

**Version:** meld_graph_v2.2.4 · PETPrep 0.0.6  
**Repository:** [github.com/phindagijimana/Meld_PET](https://github.com/phindagijimana/Meld_PET)  
**Orchestration:** Snakemake · **CLI:** `meldpet`

---

## 1. Purpose

The **meldpet** pipeline combines:

1. **MELD Graph** — surface-based graph neural network lesion prediction on structural MRI (T1w).
2. **PETPrep** — BIDS-compliant FDG-PET preprocessing.
3. **Registration & statistics** — rigid alignment of PET into MELD/FreeSurfer space, PET↔lesion asymmetry metrics, and cohort concordance roll-up.
4. **Visualization** — headless overlay figures (T1, PET, MELD prediction).

Design lineage: [Meld_CBF](https://github.com/phindagijimana/Meld_CBF) (same registration and stats pattern; PET instead of CBF).

---

## 2. Pipeline overview

Each subject with BIDS PET + T1w runs through six stages:

| Stage | What it does | Container |
|-------|--------------|-----------|
| **prepare** | Stage T1w into MELD input tree | host |
| **petprep** | Preprocess PET; produce T1w-space reference | PETPrep |
| **meld** | FreeSurfer recon + graph lesion prediction | MELD Graph |
| **register** | PET → MELD grid; compute PET↔lesion stats | MELD Graph |
| **visualize** | PNG overlays | MELD Graph |
| **aggregate** | Cohort CSV + concordance call | host (pandas) |

**Parallel branches:** After `prepare`, **PETPrep** and **MELD** run independently and can be scheduled in parallel on SLURM. Fusion happens only in **register**, once both branches finish.

```
BIDS (PET + T1w)
    │
prepare ──► MELD input (T1w only by default)
    │
    ├── petprep ──► work/pet/<sub>_pet.nii.gz
    │
    └── meld ─────► prediction.nii.gz + T1.mgz + aparc+aseg.mgz
              │
              ▼
         register ──► pet_in_meld.nii.gz + prediction_in_meld.nii.gz + stats CSV
              │
              ▼
         visualize ──► figures/*.png
              │
              ▼
         aggregate ──► pet_cohort_stats.csv
```

---

## 3. MELD uses T1w only (default)

By default **`meld_t1_only: true`** in `config.yaml`:

- Only T1w is staged to `work/input/<sub>/T1/`.
- FLAIR paths in `samples.tsv` are **not** passed to MELD, even if present in BIDS.
- FreeSurfer runs: `recon-all -i T1w.nii.gz -all` (no `-FLAIR`).

To include FLAIR in MELD segmentation, set `meld_t1_only: false`.

---

## 4. Coordinate spaces and registration

PETPrep and MELD each produce images in related but distinct anatomical spaces. Statistics and overlays require a **shared voxel grid**.

```
BIDS native T1w          PETPrep output              MELD / FreeSurfer
───────────────          ──────────────              ─────────────────
sub_*_T1w.nii.gz   →     *_space-T1w*preproc_pet*   T1.mgz (conformed 256³)
                         (rigid to BIDS T1w)         prediction.nii.gz (native T1w)
                                                     ↓ resampled to T1.mgz grid
                                                     prediction_in_meld.nii.gz
                              │
                              │  mri_coreg + mri_vol2vol
                              └──────────► pet_in_meld.nii.gz
```

**Register** (`pet_register_in_container.sh`):

1. `mri_coreg` — 6-DOF rigid PET → `T1.mgz`.
2. `mri_vol2vol` — trilinear resampling → `pet_in_meld.nii.gz`.
3. Nearest-neighbor resample of native `prediction.nii.gz` → **`prediction_in_meld.nii.gz`** (same grid as `T1.mgz`).
4. `pet_stats.py` — asymmetry and concordance on the shared grid.

---

## 5. Inputs and cohort setup

### 5.1 BIDS layout (minimum)

```
bids_root/
└── sub-XXX/
    └── ses-N/
        ├── anat/
        │   └── sub-XXX_ses-N_T1w.nii.gz    # required
        └── pet/
            └── sub-XXX_ses-N_pet.nii.gz    # required for PETPrep
```

### 5.2 Mapping files

| File | Purpose |
|------|---------|
| `PET_BIDS_SUB.csv` | `EP_ID` ↔ `BIDS_ID` cohort list |
| `PET_session_resolution.csv` | Optional: PET/T1 session pairing per subject |
| `pipeline/config/samples.tsv` | Built by `meldpet samples` |

Use the T1w session **contemporaneous with PET** when possible.

### 5.3 Site configuration

Copy `pipeline/config/config.example.yaml` → `pipeline/config/config.yaml`.

| Key | Role |
|-----|------|
| `bids_root` | BIDS dataset (read-only in PETPrep) |
| `work` | Pipeline outputs; mounted as `/data` in MELD container |
| `petprep_out` | PETPrep derivatives |
| `petprep_sif` | Apptainer image or `docker://ghcr.io/nipreps/petprep:0.0.6` |
| `sif` | MELD Graph `.sif` (v2.2.4) |
| `meld_t1_only` | `true` = T1-only MELD (default) |
| `tracer_mode` | `deficit` (hypometabolism) or `excess` |
| `abnormal_z`, `asym_concordance_pct`, `dice_concordance` | Stats thresholds |

Validate: `meldpet check`

---

## 6. Key outputs

Per subject (`work/output/`):

| Path | Description |
|------|-------------|
| `fs_outputs/<sub>/mri/T1.mgz` | MELD conformed T1 |
| `predictions_reports/<sub>/predictions/prediction.nii.gz` | MELD lesion map (native T1w space) |
| `pet_aligned/<sub>/pet_in_meld.nii.gz` | PET on MELD grid |
| `pet_aligned/<sub>/prediction_in_meld.nii.gz` | Lesion map on MELD grid |
| `pet_aligned/<sub>/pet_in_clusters_<sub>.csv` | PET↔lesion statistics |
| `pet_aligned/<sub>/figures/*.png` | Overlay figures |
| `predictions_reports/<sub>/reports/MELD_report_<sub>.pdf` | MELD PDF report |

Cohort:

| Path | Description |
|------|-------------|
| `pet_cohort_stats.csv` | All subjects + concordance columns |

---

## 7. Statistics

Computed in **`pet_stats.py`** inside the MELD container on the shared grid.

### Per-lesion metrics

| Metric | Column | Meaning |
|--------|--------|---------|
| Lesion PET intensity | `pet_mean`, `gm_z` | Mean uptake; z-score vs cortical GM |
| ROI asymmetry | `roi_asym_pct`, `host_roi_name` | Lesion ROI vs FreeSurfer homologue |
| Mirror asymmetry | `cluster_mirror_ai` | Lesion vs L↔R-flipped mask |
| Spatial concordance | `frac_abnormal`, `dice_abnormal` | Overlap with tracer-abnormal GM |

### Tracer modes

- **`deficit`** — lower uptake is abnormal (FDG hypometabolism). Concordant when `roi_asym_pct ≤ asym_concordance_pct` (default −8%).
- **`excess`** — higher uptake is abnormal.

### Concordance call (`aggregate`)

On the `all_clusters` row:

| Value | Meaning |
|-------|---------|
| `concordant` | Tracer + spatial criteria both met |
| `partial` | One criterion met |
| `discordant` | Neither met |

**Note:** Subjects with `cluster=none` (MELD negative) show `discordant` in the cohort table — this is a labeling artifact, not real PET–MRI discordance.

---

## 8. CLI reference

```bash
# Setup
meldpet check
meldpet samples

# Full run
meldpet run sub-002 sub-036 sub-065
meldpet run --profile slurm -j 6
meldpet run --aggregate

# Individual stages
meldpet prepare | petprep | meld | register | visualize | aggregate

# Monitoring
meldpet status
meldpet dag -o dag.svg
```

---

## 9. SLURM execution

```bash
meldpet run --profile slurm -j 6
```

Default resource hints:

| Rule | Memory | CPUs | Time |
|------|--------|------|------|
| prepare | 4 GB | 1 | 20 min |
| petprep | 32 GB | 4 | 16 h |
| meld | 64 GB | 8 | 24 h |
| register | 16 GB | 2 | 2 h |
| visualize | 8 GB | 1 | 30 min |

Interactive partition (≤12 h): `pipeline/profiles/interactive/` + `pipeline/scripts/run_interactive.sh`

---

## 10. Pilot cohort results (T1-only MELD)

Processed subjects: **sub-002**, **sub-036**, **sub-065** (CIDUR BIDS).

| Subject | MELD lesion | Location | PET vs MELD (deficit mode) |
|---------|-------------|----------|----------------------------|
| sub-002 | Yes (10,241 vox) | Bilateral temporal | Mild hypometabolism (`gm_z ≈ −0.9`); discordant under strict thresholds |
| sub-036 | No | — | Normal PET; expected negative screen |
| sub-065 | Yes (1,530 vox) | Right precuneus | Hypermetabolic (`gm_z ≈ +1.1`); discordant with deficit assumptions |

**Caveat (sub-065):** MELD T1 from ses-1; PET staged from ses-2 (only session with T1w-space preproc PET). Review session pairing if interpreting concordance.

Deliverables on NAS: `smb://smdnas/gugger_lab/Workflows/MELD_PET`

```
MELD_PET/
├── pet_cohort_stats.csv
├── sub-002/  pet_aligned/  predictions_reports/  logs/
├── sub-036/  ...
└── sub-065/  ...
```

---

## 11. Repository layout

```
Meld_PET/
├── meldpet.md                  ← this document
├── Meld_PET.md                 ← extended technical reference
├── README.md
├── pipeline/
│   ├── meldpet/cli.py          ← meldpet command
│   ├── config/config.yaml      ← site config (local)
│   ├── workflow/Snakefile + rules/
│   ├── pet_register_in_container.sh
│   ├── pet_stats.py
│   ├── pet_visualize.py
│   └── profiles/slurm/
└── work/                       ← outputs (not in git)
```

---

## 12. Citations

**MELD Graph:** Ripart M, Spitzer H, et al. *JAMA Neurology* 2025; Spitzer H, et al. *Brain* 2022; Spitzer H, et al. MICCAI 2023.

**PETPrep:** Nørgaard M, Markiewicz CJ, Esteban O, et al. [petprep.readthedocs.io](https://petprep.readthedocs.io)

**BIDS:** Gorgolewski KJ, et al. *Scientific Data* 2016.

**Snakemake:** Köster J, Rahmann S. *Bioinformatics* 2012.

**FreeSurfer:** Fischl B, et al. *NeuroImage* 1999.

Full reference list: see `README.md` in the repository.

---

*Document generated for the Gugger Lab MELD_PET workflow. Last updated: June 2026.*

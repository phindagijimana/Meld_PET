# MELD + PET pipeline

Runs **MELD Graph** lesion prediction on T1w, **PETPrep** on BIDS PET+T1w, registers PET into MELD space, and computes asymmetry and concordance statistics with cohort roll-up.

Orchestrated by **Snakemake** and driven by the **`meldpet` CLI**.

## Install

```bash
cd Meld_PET/pipeline
conda env create -f workflow/envs/meldpet.yaml && conda activate meldpet
pip install -e .
cp config/config.example.yaml config/config.yaml   # edit paths for your site
```

## Quick start

```bash
meldpet check
meldpet samples
meldpet run sub-002
meldpet run --profile slurm
meldpet aggregate
meldpet status
```

## Key outputs (`work/output/`)

- `pet_aligned/<sub>/pet_in_meld.nii.gz` — PET on the MELD prediction grid
- `pet_aligned/<sub>/pet_in_clusters_<sub>.csv` — per-lesion PET stats
- `pet_aligned/<sub>/figures/*.png` — T1 / PET / prediction overlays
- `pet_cohort_stats.csv` — cohort table + concordance call

## Documentation

- **[Meld_PET.md](Meld_PET.md)** — full pipeline reference (architecture, stages, diagrams)
- **[pipeline/USER_GUIDE.md](pipeline/USER_GUIDE.md)** — setup, CLI, config, statistics, SLURM
- **[meld.md](meld.md)** — MELD container implementation
- **[petprep.md](petprep.md)** — PETPrep container implementation

## Citation

If you use this pipeline, please cite the underlying methods and software:

**MELD Graph** (lesion prediction):

- Ripart M, Spitzer H, et al. Detection of epileptogenic focal cortical dysplasia using graph neural networks: a MELD study. *JAMA Neurology*. 2025. [https://jamanetwork.com/journals/jamaneurology/fullarticle/2830410](https://jamanetwork.com/journals/jamaneurology/fullarticle/2830410)
- Spitzer H, Ripart M, et al. Interpretable surface-based neural network for the MELD FCD classifier. *Brain*. 2022. [https://doi.org/10.1093/brain/awac224](https://doi.org/10.1093/brain/awac224)
- Spitzer H, Ripart M, et al. A graph U-net model for segmentation of focal cortical dysplasia lesions. *MICCAI*. 2023. [https://arxiv.org/abs/2306.01375](https://arxiv.org/abs/2306.01375)

**PETPrep** (PET preprocessing):

- Nørgaard M, Markiewicz CJ, Esteban O, et al. PETPrep: a robust preprocessing pipeline for PET data. Software; documentation and citation boilerplate: [https://petprep.readthedocs.io](https://petprep.readthedocs.io). Repository: [https://github.com/nipreps/petprep](https://github.com/nipreps/petprep). Use the citation text from each subject’s PETPrep HTML report in publications.

**Standards and orchestration:**

- Gorgolewski KJ, et al. The brain imaging data structure. *Scientific Data*. 2016. [https://doi.org/10.1038/sdata.2016.44](https://doi.org/10.1038/sdata.2016.44)
- Köster J, Rahmann S. Snakemake — a scalable bioinformatics workflow engine. *Bioinformatics*. 2012. [https://doi.org/10.1093/bioinformatics/bts480](https://doi.org/10.1093/bioinformatics/bts480)

**Tools used in registration and statistics** (via MELD Graph / PETPrep containers):

- FreeSurfer — Fischl B, et al. *NeuroImage*. 1999. [https://doi.org/10.1006/nimg.1998.0395](https://doi.org/10.1006/nimg.1998.0395) (`recon-all`, `mri_coreg`, `aparc+aseg`)
- NiPreps framework — Markiewicz CJ, et al. *Nature Methods*. 2021. [https://doi.org/10.1038/s41592-021-01116-2](https://doi.org/10.1038/s41592-021-01116-2) (PETPrep follows NiPreps/BIDS-Apps conventions)
- nibabel / nilearn — used in `pet_stats.py` and `pet_visualize.py` for in-grid asymmetry and overlays

Full PETPrep tool citations (FSL, ANTs, AFNI, PETPVC, etc.): [nipreps/petprep REFERENCES.md](https://github.com/nipreps/petprep/blob/main/REFERENCES.md).

Patient data and site-specific paths are not committed — see `.gitignore`.

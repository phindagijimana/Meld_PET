# MELD + PET — pipeline quick start

See the [root README](../README.md) for install. Full reference: [USER_GUIDE.md](USER_GUIDE.md).

## CLI

```bash
meldpet check
meldpet samples
meldpet run sub-002
meldpet run --aggregate sub-002
meldpet run --profile slurm -j 16
meldpet status
meldpet aggregate
meldpet dag -o dag.svg
```

Stage subcommands: `prepare`, `petprep`, `meld`, `register`, `visualize`.

## Config

Edit `config/config.yaml` (from `config.example.yaml`):

- `bids_root` — BIDS dataset with PET + T1w
- `petprep_sif`, `sif` — Apptainer images
- `fs_license`, `meld_license` — license files
- `models_src`, `meld_params_src` — shared MELD assets
- `mapping` — EP_ID ↔ BIDS_ID CSV
- `tracer_mode`, `abnormal_z`, concordance thresholds

## SLURM

```bash
meldpet run --profile slurm -j 10
```

Profile: `profiles/slurm/config.yaml`.

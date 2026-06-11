"""
aggregate_stats.py — Snakemake script. Concatenate per-subject PET stats and add
a tracer-aware concordance call on the whole-lesion (`all_clusters`) row.

Concordance logic (thresholds from config):
  tracer_deficit  = roi_asym_pct <= asym_concordance_pct   (ipsilateral deficit)
  tracer_excess   = roi_asym_pct >= -asym_concordance_pct  (ipsilateral excess)
  spatial_concordant = dice_abnormal >= dice_concordance
  concordance_call   = concordant / partial / discordant
"""
import sys

import pandas as pd

inputs = list(snakemake.input.csvs)
asym_thr = float(snakemake.params.asym)
dice_thr = float(snakemake.params.dice)
tracer_mode = str(snakemake.params.tracer_mode)
allow_partial = bool(snakemake.params.allow_partial)
expected = int(snakemake.params.expected)
out_csv = snakemake.output.csv
pipeline_version = snakemake.params.pipeline_version

frames = []
read_errors = []
for p in inputs:
    try:
        df = pd.read_csv(p)
        if df.empty:
            read_errors.append(f"{p}: empty")
            continue
        frames.append(df)
    except Exception as exc:  # noqa: BLE001
        read_errors.append(f"{p}: {exc}")

if read_errors:
    for msg in read_errors:
        print(f"[aggregate][WARN] {msg}", file=sys.stderr)

if not frames:
    print("[aggregate][ERROR] no readable per-subject stats", file=sys.stderr)
    sys.exit(1)

if not allow_partial and len(frames) < expected:
    print(
        f"[aggregate][ERROR] only {len(frames)}/{expected} subject(s) ready "
        f"(allow_partial_aggregate=false)",
        file=sys.stderr,
    )
    sys.exit(1)


def call_row(r):
    asym = pd.to_numeric(r.get("roi_asym_pct"), errors="coerce")
    dice = pd.to_numeric(r.get("dice_abnormal"), errors="coerce")
    mode = str(r.get("tracer_mode", tracer_mode))
    if mode == "excess":
        tracer_ok = pd.notna(asym) and asym >= -asym_thr
    else:
        tracer_ok = pd.notna(asym) and asym <= asym_thr
    spat = pd.notna(dice) and dice >= dice_thr
    return pd.Series({
        "tracer_concordant": bool(tracer_ok),
        "spatial_concordant": bool(spat),
        "concordance_call": ("concordant" if (tracer_ok and spat)
                             else "partial" if (tracer_ok or spat)
                             else "discordant"),
    })


cohort = pd.concat(frames, ignore_index=True)
cohort = pd.concat([cohort, cohort.apply(call_row, axis=1)], axis=1)
cohort["pipeline_version"] = pipeline_version
cohort.to_csv(out_csv, index=False)

lesion = cohort[cohort["cluster"] == "all_clusters"]
n = len(lesion)
conc = int((lesion["concordance_call"] == "concordant").sum())
part = int((lesion["concordance_call"] == "partial").sum())
print(f"[aggregate] {len(cohort)} rows from {len(frames)}/{expected} subject(s) -> {out_csv}")
print(f"[aggregate] lesion-level concordance ({tracer_mode}): {conc}/{n} concordant, "
      f"{part}/{n} partial (asym thr={asym_thr}, dice>={dice_thr})")

#!/usr/bin/env python3
"""
build_samples.py — generate samples.tsv for the MELD + PET Snakemake workflow.

For every BIDS_ID in the EP↔BIDS mapping it resolves:
  - session : PET-contemporaneous BIDS session (optional resolution CSV, else fallback)
  - t1w     : required BIDS T1w
  - flair   : optional BIDS FLAIR

PET paths come from PETPrep derivatives after `meldpet petprep`; this sheet only
needs anatomical inputs for staging and MELD.

Usage:
  build_samples.py --config config/config.yaml [--out path] [--quiet]
"""
import argparse
import csv
import glob
import os
import sys

import yaml


def first_glob(pattern):
    hits = sorted(glob.glob(pattern))
    return hits[0] if hits else ""


def load_mapping(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r.get("BIDS_ID"):
                rows.append((r["EP_ID"], r["BIDS_ID"]))
    return rows


def load_resolution(path):
    sess = {}
    if path and os.path.isfile(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                if r.get("BIDS_ID") and r.get("resolved_session"):
                    sess[r["BIDS_ID"]] = r["resolved_session"]
    return sess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    with open(a.config) as f:
        cfg = yaml.safe_load(f)

    out = a.out or cfg["samples"]
    bids_root = cfg["bids_root"]
    fallback = cfg.get("fallback_session", "ses-1")

    mapping = load_mapping(cfg["mapping"])
    resolved = load_resolution(cfg.get("resolution_csv") or "")

    rows, kept, dropped = [], 0, 0
    for ep, sub in mapping:
        ses = resolved.get(sub, fallback)
        t1 = first_glob(f"{bids_root}/{sub}/{ses}/anat/{sub}_{ses}_T1w.nii.gz")
        if not t1:
            t1 = first_glob(f"{bids_root}/{sub}/ses-*/anat/{sub}_ses-*_T1w.nii.gz")
        flair = first_glob(f"{bids_root}/{sub}/{ses}/anat/{sub}_{ses}_FLAIR.nii.gz")

        pet_dir = first_glob(f"{bids_root}/{sub}/{ses}/pet")
        if not t1:
            dropped += 1
            if not a.quiet:
                print(f"[samples] DROP {sub} ({ep}): missing T1w", file=sys.stderr)
            continue
        if not pet_dir and not a.quiet:
            print(f"[samples][WARN] {sub}: no BIDS pet/ folder under {ses} "
                  f"(PETPrep may still work if PET exists elsewhere in BIDS)", file=sys.stderr)

        rows.append({"bids_id": sub, "ep_id": ep, "session": ses,
                     "t1w": t1, "flair": flair})
        kept += 1

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fields = ["bids_id", "ep_id", "session", "t1w", "flair"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    print(f"[samples] wrote {kept} sample(s) -> {out}  ({dropped} dropped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

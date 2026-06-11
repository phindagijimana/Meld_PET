#!/usr/bin/env python3
"""
stage_pet_bids.py — convert raw PETMR DICOM to BIDS pet/ under CIDUR_BIDS.

Uses dcm2niix on attenuation-corrected dynamic PET (30003 series).
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

# EP_ID -> AC PET DICOM directory (attenuation-corrected dynamic series)
PET_DICOM = {
    "EP019523": "CIDUR_data/EP019523/EP019523/EP019523_PETMR_1/scans/30003-_Head_PetAcquisition_AC_Images/resources/DICOM/files",
    "EP458826": "CIDUR_data/EP458826/EP458826/EP458826_PETMR_1/scans/30003-_Head_PetAcquisition_AC_Images/resources/DICOM/files",
    "EP808593": "CIDUR_data/EP808593/EP808593/EP808593_PETMR_1/scans/30003-_Head_PetAcquisition_AC_Images/resources/DICOM/files",
}


def load_mapping(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r.get("BIDS_ID") and r.get("EP_ID"):
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


def patch_pet_json(json_path):
    with open(json_path) as f:
        meta = json.load(f)
    meta.setdefault("Modality", "PET")
    meta.setdefault("Manufacturer", meta.get("Manufacturer", "SIEMENS"))
    # BIDS PET sidecar hints for FDG static/dynamic pipelines
    if "TracerName" not in meta:
        meta["TracerName"] = "FDG"
    if "TracerRadionuclide" not in meta:
        meta["TracerRadionuclide"] = "F18"
    with open(json_path, "w") as f:
        json.dump(meta, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--documents-root", default="/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    with open(a.config) as f:
        cfg = yaml.safe_load(f)

    bids_root = cfg["bids_root"]
    mapping = load_mapping(cfg["mapping"])
    resolved = load_resolution(cfg.get("resolution_csv") or "")
    fallback = cfg.get("fallback_session", "ses-1")
    docs = a.documents_root

    dcm2niix = shutil.which("dcm2niix")
    if not dcm2niix:
        print("[stage_pet_bids][ERROR] dcm2niix not on PATH", file=sys.stderr)
        return 1

    ok, fail = 0, 0
    for ep, sub in mapping:
        ses = resolved.get(sub, fallback)
        rel = PET_DICOM.get(ep)
        if not rel:
            print(f"[stage_pet_bids][ERROR] no PET DICOM path for {ep}", file=sys.stderr)
            fail += 1
            continue
        dicom_dir = os.path.join(docs, rel)
        if not os.path.isdir(dicom_dir):
            print(f"[stage_pet_bids][ERROR] missing DICOM: {dicom_dir}", file=sys.stderr)
            fail += 1
            continue

        pet_dir = os.path.join(bids_root, sub, ses, "pet")
        os.makedirs(pet_dir, exist_ok=True)
        out_nii = os.path.join(pet_dir, f"{sub}_{ses}_pet.nii.gz")
        out_json = os.path.join(pet_dir, f"{sub}_{ses}_pet.json")

        if os.path.isfile(out_nii):
            print(f"[stage_pet_bids] skip {sub} (exists): {out_nii}")
            ok += 1
            continue

        with tempfile.TemporaryDirectory(prefix="pet_bids_") as tmp:
            cmd = [dcm2niix, "-z", "y", "-f", f"{sub}_{ses}_pet", "-o", tmp, dicom_dir]
            if not a.quiet:
                print(f"[stage_pet_bids] {sub}: dcm2niix ...")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                print(proc.stderr or proc.stdout, file=sys.stderr)
                fail += 1
                continue
            hits = [f for f in os.listdir(tmp) if f.endswith(".nii.gz")]
            if not hits:
                print(f"[stage_pet_bids][ERROR] no NIfTI for {sub}", file=sys.stderr)
                fail += 1
                continue
            src_nii = os.path.join(tmp, hits[0])
            src_json = src_nii.replace(".nii.gz", ".json")
            shutil.copyfile(src_nii, out_nii)
            if os.path.isfile(src_json):
                shutil.copyfile(src_json, out_json)
                patch_pet_json(out_json)
        print(f"[stage_pet_bids] wrote {out_nii}")
        ok += 1

    print(f"[stage_pet_bids] done: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

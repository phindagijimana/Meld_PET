# MELD Graph: container implementation

This document ties together the **official MELD Graph container** from [MELDProject/meld_graph](https://github.com/MELDProject/meld_graph) and the **local deployment layer** in `docker_version/meld-docker` (Apptainer/Singularity wrapper for HPC).

On your NFS layout, the executable wrapper and `production.env.example` currently live under a **MELD Graph** checkout (for example next to this folder under `Documents/Meld_Graph/docker_version/`). The path in the code citation below matches that layout; adjust if you copy `docker_version/` into `Meld_PET` or another project root.

Full upstream docs: [MELD Graph on Read the Docs](https://meld-graph.readthedocs.io/en/latest/index.html). Docker install guide: [install_docker.html](https://meld-graph.readthedocs.io/en/latest/install_docker.html). HPC/Singularity: [install_singularity.html](https://meld-graph.readthedocs.io/en/latest/install_singularity.html).

---

## What the upstream project ships

[MELD Graph](https://github.com/MELDProject/meld_graph) is the graph-based FCD lesion segmentation pipeline for the MELD project. The **container image** bundles OS dependencies, FreeSurfer, FastSurfer, the `meld_graph` Conda environment, PyTorch / PyG stack, and the application code under `/app`.

### Image build (`Dockerfile`)

The repository’s `Dockerfile` is a **multi-stage** build (see the file on GitHub for exact versions):

1. **Micromamba stage** — From `mambaorg/micromamba`, creates the `meld_graph` environment from `environment.yml`, then cleans caches.
2. **Runtime stage (`MELDgraph`)** — Based on `debian:12-slim`:
   - Downloads and unpacks **FreeSurfer 7.2** under `/opt/freesurfer-7.2.0` (with selective excludes to shrink the image).
   - Installs base packages (`gcc`, `git`, `python3`, etc.).
   - Sets `FREESURFER_HOME`, `PATH`, and documents **`FS_LICENSE=/license.txt`** in the image’s shell init.
   - Clones **FastSurfer** (pinned branch, e.g. v1.1.2) into `/opt/fastsurfer-v1.1.2` and sets `FASTSURFER_HOME`.
   - Copies the **micromamba-created** `/opt/conda/envs/meld_graph` from the first stage.
   - **`COPY . .`** into `/app` (the meld_graph source tree).
   - Runs `micromamba run -n meld_graph` to **pip install** pinned `torch` / `torchvision`, editable install of the package, `torch-scatter`, `torch-geometric`, `captum`, and activates `meld_graph` in bash.
   - Creates **`/data`** for mounted patient data, plus writable cache-style directories used by FreeSurfer/FastSurfer.
   - **`ENTRYPOINT ["/bin/bash","entrypoint.sh"]`**.

Published images are pushed under names such as `meldproject/meld_graph:<tag>` (see [Releases](https://github.com/MELDProject/meld_graph/releases)).

### Container entrypoint (`entrypoint.sh`)

The entrypoint sources FreeSurfer (`$FREESURFER_HOME/FreeSurferEnv.sh`) and then executes the command passed to the container (`$@`). That matches the documented pattern: the “real” work is always whatever you pass after the image name (`docker compose run …`, `docker run …`, or Apptainer `exec` with a bash `-c` string).

### Docker Compose (`compose.yml`)

For workstation Docker, the repo provides `compose.yml` that:

- Pulls **`meldproject/meld_graph`** (pinned tag in practice).
- Mounts a host data directory to **`/data`** inside the container.
- Supplies **FreeSurfer** and **MELD** licenses via **Docker secrets**, exposed as files with paths set in **`FS_LICENSE`** and **`MELD_LICENSE`**.
- Optionally reserves GPUs via `deploy.resources` (GPU-specific image tags exist upstream).

Users run setup steps such as `prepare_classifier.py` and `pytest` through `docker compose run meld_graph …` as described in the [Docker installation page](https://meld-graph.readthedocs.io/en/latest/install_docker.html).

---

## Local layer: `docker_version/meld-docker`

Your tree adds **`docker_version/meld-docker`**: a **bash driver** (not Docker Desktop on the cluster) that runs the **same** software as the official image, packaged as an **Apptainer/Singularity `.sif`** built from that image.

### Why a wrapper script

- **HPC** sites often disallow Docker; **Apptainer/Singularity** is the supported path ([install_singularity](https://meld-graph.readthedocs.io/en/latest/install_singularity.html)).
- The script encodes the **official invocation**: `cd /app`, source `FreeSurferEnv.sh`, then `python scripts/new_patient_pipeline/new_pt_pipeline.py …`.
- It centralizes **bind mounts**, **license paths**, **data layout**, **logging**, **file locks**, and optional **SLURM** submission.

### Standard bundle layout

As documented in `docker_version/production.env.example`, a portable deploy directory typically contains:

- `meld-docker` — main CLI.
- `meld_production.sh` — thin wrapper that forwards to `meld-docker` with optional command aliases (`sync`, `run-cohort`, `slurm-cohort`).
- `meld_graph_v2.2.4.sif` — Apptainer image built from Docker, e.g.  
  `apptainer build meld_graph_v2.2.4.sif docker://meldproject/meld_graph:v2.2.4`
- `freesurfer_license.txt`, `meld_license.txt` — host copies bound into the container.
- `meld_data/` — host tree bound to **`/data`**, including `input/`, `output/`, `logs/`, `locks/`, `models/`, `meld_params/`, and cohort folders with BIDS-style subjects.

Optional `production.env` can override roots (split NFS volumes for code vs data, explicit `MELD_CONTAINER_IMAGE`, `MELD_DATA_DIR`, `MODELS_SRC`, `MELD_PARAMS_SRC`, SLURM defaults).

### How a run is executed (`run_container`)

Conceptually each pipeline run does:

1. **`apptainer exec`** on the `.sif` (with **`singularity`/`apptainer`** detected on `PATH`).
2. **`--bind "${MELD_DATA_DIR}:/data"`** so the pipeline reads/writes the same layout the native/Docker docs expect under `/data`.
3. Optional read-only binds for **`meld_params`** and **`models`** when they live outside `MELD_DATA_DIR`.
4. Binds host license files to **`/license.txt`** and **`/meld_license.txt`**, with **`FS_LICENSE`** / **`MELD_LICENSE`** set accordingly (matching Docker secret paths inside the container).
5. Sets **`PYTHONNOUSERSITE=1`** so user-level `~/.local` packages on the host cannot override the image’s NumPy/Py stack inside the container.
6. Runs **`/bin/bash -c "cd /app && source \$FREESURFER_HOME/FreeSurferEnv.sh && <command>"`**.

The `run_container` function in your `docker_version/meld-docker` script implements the bind mounts and inner bash command (example path: a `Meld_Graph` checkout on your NFS home):

```352:383:/mnt/nfs/home/URMC-SH/pndagiji/Documents/Meld_Graph/docker_version/meld-docker
run_container() {
    local cmd="$*"

    # Build optional extra bind mounts for meld_params / models when they
    # live outside MELD_DATA_DIR (e.g. shared across cohorts on NFS).
    local extra_binds=()
    if [[ -n "${MELD_PARAMS_SRC}" ]]; then
        extra_binds+=(--bind "${MELD_PARAMS_SRC}:/data/meld_params:ro")
    fi
    if [[ -n "${MODELS_SRC}" ]]; then
        extra_binds+=(--bind "${MODELS_SRC}:/data/models:ro")
    fi

    # The container ships numpy 1.22.0 (correct, compatible with pandas 1.4.1).
    # However, if the user has a newer numpy installed in ~/.local (user-level
    # pip), Python inside the container will find it first and override the
    # container's numpy, causing a binary ABI incompatibility.
    # PYTHONNOUSERSITE=1 prevents Python from reading ~/.local/lib/python*/
    # site-packages inside the container, ensuring the container's own
    # numpy 1.22.0 is always used.
    apptainer exec \
        --bind "${MELD_DATA_DIR}:/data" \
        "${extra_binds[@]}" \
        --bind "${FS_LICENSE}:/license.txt:ro" \
        --bind "${MELD_LICENSE}:/meld_license.txt:ro" \
        --env FS_LICENSE=/license.txt \
        --env MELD_LICENSE=/meld_license.txt \
        --env FREESURFER_HOME=/opt/freesurfer-7.2.0 \
        --env PYTHONNOUSERSITE=1 \
        "${CONTAINER_IMAGE}" \
        /bin/bash -c "cd /app && source \$FREESURFER_HOME/FreeSurferEnv.sh && ${cmd}"
}
```

The default pipeline command is:

`python scripts/new_patient_pipeline/new_pt_pipeline.py -id <subject> [flags]`

Flags such as `--fastsurfer`, `-harmo_code`, etc. are passed through from the CLI.

### Commands exposed by `meld-docker`

The script implements subcommands including **`check`**, **`run`**, **`batch`**, **`cohort`** (sync/run/slurm workflows), **`status`**, **`validate`**, **`logs`**, **`results`**, **`shell`**, **`slurm`** / **`slurm cohort`**, and **`version`**. **`check`** validates runtime, image path, licenses, `meld_params`, `models`, disk space, and SLURM availability.

### SLURM integration

`slurm`-style commands submit **`sbatch`** jobs whose wrap script **`cd`s** to the script directory and invokes **`./meld-docker run`** so each job uses the same container invocation and logging as an interactive node.

---

## Mental model: one image, two front-ends

| Aspect | Upstream Docker workflow | `docker_version/meld-docker` |
|--------|--------------------------|------------------------------|
| Orchestrator | Docker Compose / `docker run` | Apptainer `exec` + bash wrapper |
| Image | OCI image from Docker Hub | `.sif` built **from** that OCI image |
| Data | Volume → `/data` | `--bind` host dir → `/data` |
| Licenses | Compose secrets | `--bind` host files → `/license.txt`, `/meld_license.txt` |
| Pipeline | Same Python entrypoint under `/app` | Same |

---

## References

- Repository: [https://github.com/MELDProject/meld_graph](https://github.com/MELDProject/meld_graph)
- Docker: [https://meld-graph.readthedocs.io/en/latest/install_docker.html](https://meld-graph.readthedocs.io/en/latest/install_docker.html)
- Singularity/Apptainer: [https://meld-graph.readthedocs.io/en/latest/install_singularity.html](https://meld-graph.readthedocs.io/en/latest/install_singularity.html)
- Local wrapper directory: **`docker_version/`** (`meld-docker`, `meld_production.sh`, `production.env.example`, smoke test helper)

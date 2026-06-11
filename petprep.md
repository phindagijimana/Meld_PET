# PETPrep: container implementation

This document explains how **containerized PETPrep** is built and run in the [nipreps/petprep](https://github.com/nipreps/petprep) project. PETPrep is a [NiPreps](https://www.nipreps.org/) BIDS App for PET preprocessing (motion correction, reference images, normalization, brain masking, registration, partial-volume correction, time–activity curves, QC reports). User-facing documentation: [petprep.readthedocs.io](https://petprep.readthedocs.io/).

---

## Distribution model

PETPrep follows **BIDS-Apps** conventions for the CLI: the same flags apply on bare metal and in containers; only the **preamble** (runtime + image + bind mounts) changes. The docs recommend **containers** over manual installs because the stack pulls in FSL, ANTs, AFNI, FreeSurfer, PETPVC, and other binaries that are awkward to reproduce by hand. See the [installation](https://github.com/nipreps/petprep/blob/main/docs/installation.rst) page in the repo (rendered on Read the Docs).

Typical ways to run:

| Method | Role |
|--------|------|
| **`petprep-docker`** | PyPI wrapper (`pip install petprep-docker`) that constructs `docker run …` with the right mounts and passes through arguments as if you ran `petprep` locally. |
| **`docker pull ghcr.io/nipreps/petprep:main`** | Pre-built application image (pin a release tag in production). On non-`linux/amd64`, use `--platform=linux/amd64` when needed. |
| **Apptainer / Singularity** | `apptainer build petprep.sif docker://ghcr.io/nipreps/petprep:main` then `apptainer run` with BIDS input, output, license, and work-dir binds (documented in installation). |

Image registry: [GitHub Packages — `ghcr.io/nipreps/petprep`](https://github.com/nipreps/petprep/pkgs/container/petprep). The README notes roughly **~24 GB** image size and **~30 GB** free disk recommended including Docker overhead.

---

## Image architecture: `Dockerfile.base` + `Dockerfile`

Build is split so a heavy **base** image can be published once and the **app** image rebuilt often.

### `Dockerfile.base` → `petprep-base`

The base recipe (Ubuntu 22.04 “Jammy”) assembles OS libraries and **non-Python** tools that PETPrep shells out to:

- **Download stages**: `curl`-based stages fetch **PETPVC** (Linux tarball into `/opt/petpvc`) and **MSM_HOCR** (`msm` binary).
- **Main `base` stage**: apt packages for FreeSurfer/PETPVC runtime deps (e.g. `bc`, ITK libs, `tcsh`, `xvfb`).
- **FreeSurfer 7.4.1**: copied from the official `freesurfer/freesurfer:7.4.1` image into `/opt/freesurfer`, with environment variables that mirror **`SetUpFreeSurfer.sh`** (`FREESURFER_HOME`, `SUBJECTS_DIR`, `PATH`, MNI/MINC paths).
- **AFNI**: only a small env hook in the base Dockerfile (`AFNI_IMSAVE_WARNINGS=NO`). Heavier toolchains (**FSL**, **ANTs**, full **AFNI**, etc.) are installed into the **`petprep`** Micromamba environment in the main `Dockerfile` (see `env.yml` / `requirements.txt`); the final image sets **`FSLDIR`** to that conda prefix so FSL and Python share one managed stack.

The application `Dockerfile` defaults to something like:

`ARG BASE_IMAGE=ghcr.io/nipreps/petprep-base:20250912`

so local `docker build` can reuse the prebuilt base from GHCR instead of rebuilding all neuroimaging dependencies every time.

### `Dockerfile` → `petprep` application image

Multi-stage build on top of `${BASE_IMAGE}`:

1. **`src` stage** — `ghcr.io/astral-sh/uv:python3.12-alpine` copies the repository and runs **`uv build --wheel`** to produce a Python wheel.
2. **`micromamba` stage** — `mambaorg/micromamba:2.3.2` creates the **`petprep`** conda environment from **`env.yml`** and **`requirements.txt`**, with retry logic for flaky network installs, then **`micromamba clean`**. Installs **Node** tools globally: **`svgo`** and **`bids-validator@1.14.10`** (reporting/QC and BIDS validation).
3. **`petprep` (final) stage** — From `petprep-base`:
   - Adds a **`petprep`** Linux user and home under `/home/petprep`.
   - Copies **`micromamba`** and the **`/opt/conda/envs/petprep`** environment; activates it in `.bashrc`.
   - Runs **`scripts/fetch_templates.py`** to **precache TemplateFlow** atlases under `~/.cache/templateflow` and fixes permissions for group/other read (typical for shared cache dirs in containers).
   - Sets **FSL-related `ENV`** with `FSLDIR` pointing at the conda env, `PYTHONNOUSERSITE=1`, and single-thread defaults **`MKL_NUM_THREADS=1`**, **`OMP_NUM_THREADS=1`** (parallelism delegated to NiPype).
   - Installs **MATLAB Compiler Runtime (MCR) R2019b** via **`fs_install_mcr`** for FreeSurfer MATLAB-dependent components.
   - **`pip install`** the built **wheel** with extras **`[container,test]`**.
   - Sets **`IS_DOCKER_8395080871=1`** for “running inside Docker” detection, **`ldconfig`**, and **`WORKDIR /tmp`**.

**`ENTRYPOINT`** is the conda-installed CLI:

`ENTRYPOINT ["/opt/conda/envs/petprep/bin/petprep"]`

So `docker run … ghcr.io/nipreps/petprep:tag <args>` is equivalent to `petprep <args>` on bare metal, matching BIDS-Apps expectations.

**Labels** (`org.label-schema.*`) record build date, git ref, version, and docs URL for provenance.

---

## Local development build

The root **`Makefile`** exposes **`make docker-build [tag=TAG]`**, which runs `docker build` with `--build-arg` for `BUILD_DATE`, `VCS_REF`, and `VERSION` (from `hatch version`). Default image tag is **`petprep`**.

---

## `wrapper/` directory

The repository includes a **`wrapper/`** subtree (separate `pyproject.toml`, `README.rst`) for the **`petprep-docker`** distribution that is published to PyPI. That wrapper is the supported way to translate `petprep …` invocations into correct Docker volume flags and FreeSurfer license handling without hand-writing long `docker run` lines. Details live in the wrapper README and NiPreps’ container execution docs linked from [installation.rst](https://github.com/nipreps/petprep/blob/main/docs/installation.rst).

---

## Practical notes

- **FreeSurfer license**: required; in Apptainer the docs show binding host `license.txt` into the container and passing **`--fs-license-file`** (path inside the container). Same idea for Docker via the wrapper or explicit `-v`.
- **TemplateFlow**: many templates are prefetched in the image; additional templates may still download at runtime depending on workflow options (cache dirs should be writable or pre-populated).
- **HPC**: use **Apptainer** with explicit **`--bind`** for BIDS root, outputs, work directory, and license, as in the [installation](https://github.com/nipreps/petprep/blob/main/docs/installation.rst) example.

---

## References

- Repository: [https://github.com/nipreps/petprep](https://github.com/nipreps/petprep)
- Documentation: [https://petprep.readthedocs.io/](https://petprep.readthedocs.io/)
- Container registry: [https://github.com/nipreps/petprep/pkgs/container/petprep](https://github.com/nipreps/petprep/pkgs/container/petprep)
- Key files: [`Dockerfile`](https://github.com/nipreps/petprep/blob/main/Dockerfile), [`Dockerfile.base`](https://github.com/nipreps/petprep/blob/main/Dockerfile.base), [`Makefile`](https://github.com/nipreps/petprep/blob/main/Makefile), [`docs/installation.rst`](https://github.com/nipreps/petprep/blob/main/docs/installation.rst), [`wrapper/`](https://github.com/nipreps/petprep/tree/main/wrapper)

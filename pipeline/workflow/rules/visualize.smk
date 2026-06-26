# visualize.smk — headless overlay PNGs (T1 + PET + prediction).
rule visualize:
    input:
        pet=pet_in_meld("{sub}"),
        pred=pred_in_meld("{sub}"),
        t1mgz=meld_t1mgz("{sub}"),
    output:
        flag=viz_flag("{sub}"),
    params:
        cmd=lambda wc: apptainer_cmd(
            f"python /pipeline/pet_visualize.py {wc.sub} "
            f"/data/output/fs_outputs/{wc.sub}/mri/T1.mgz "
            f"/data/output/pet_aligned/{wc.sub}/prediction_in_meld.nii.gz "
            f"/data/output/pet_aligned/{wc.sub}/pet_in_meld.nii.gz "
            f"/data/output/pet_aligned/{wc.sub}/figures"
        ),
    log:
        os.path.join(LOG_DIR, "visualize_{sub}.log"),
    resources:
        mem_mb=res("visualize", "mem_mb", 8000),
        runtime=res("visualize", "runtime", 30),
        cpus_per_task=res("visualize", "cpus_per_task", 1),
    shell:
        "{params.cmd} > {log} 2>&1 && touch {output.flag}"

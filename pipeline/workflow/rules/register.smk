# register.smk — rigid PET -> MELD T1 registration + asymmetry/concordance stats.
rule register:
    input:
        pred=meld_pred("{sub}"),
        t1mgz=meld_t1mgz("{sub}"),
        pet=pet_staged("{sub}"),
    output:
        pet_out=pet_in_meld("{sub}"),
        pred_out=pred_in_meld("{sub}"),
        csv=pet_stats_csv("{sub}"),
    params:
        cmd=lambda wc: apptainer_cmd(
            "bash /pipeline/pet_register_in_container.sh "
            f"{wc.sub} {config['tracer_mode']} {config['abnormal_z']}"
        ),
    log:
        os.path.join(LOG_DIR, "register_{sub}.log"),
    resources:
        mem_mb=res("register", "mem_mb", 16000),
        runtime=res("register", "runtime", 120),
        cpus_per_task=res("register", "cpus_per_task", 2),
    shell:
        "{params.cmd} > {log} 2>&1"

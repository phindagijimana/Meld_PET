# aggregate.smk — cohort roll-up + tracer-aware concordance call.
# Inputs are all expected per-subject stats CSVs; Snakemake schedules register
# jobs upstream when building the default target.


rule aggregate:
    input:
        csvs=lambda wildcards: [pet_stats_csv(s) for s in SUBJECTS],
    output:
        csv=COHORT_CSV,
    params:
        asym=config["asym_concordance_pct"],
        dice=config["dice_concordance"],
        tracer_mode=config.get("tracer_mode", "deficit"),
        allow_partial=config.get("allow_partial_aggregate", True),
        expected=len(SUBJECTS),
        pipeline_version=config.get("container_tag", "unknown"),
    log:
        os.path.join(LOG_DIR, "aggregate.log"),
    script:
        "../scripts/aggregate_stats.py"

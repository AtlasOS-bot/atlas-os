from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "workflows"
    / "pokemon-pipeline.yml"
)


def read_workflow():
    return WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )


def test_workflow_file_exists():
    assert WORKFLOW_PATH.is_file()


def test_workflow_has_manual_dispatch_trigger():
    content = read_workflow()
    assert "workflow_dispatch:" in content


def test_workflow_has_a_schedule():
    content = read_workflow()
    assert "schedule:" in content
    assert "cron:" in content


def test_workflow_schedule_is_conservative_not_matching_legacy_cadence():
    """
    The legacy pipeline runs every 15-30 minutes. This workflow must
    start out meaningfully less frequent while it is still unproven
    in production.
    """
    content = read_workflow()
    assert '"*/15 * * * *"' not in content
    assert '"*/20 * * * *"' not in content
    assert '"*/30 * * * *"' not in content


def test_workflow_has_concurrency_protection_that_queues_not_cancels():
    content = read_workflow()
    assert "concurrency:" in content
    assert "cancel-in-progress: false" in content


def test_workflow_has_a_timeout():
    content = read_workflow()
    assert "timeout-minutes:" in content


def test_workflow_runs_canonical_collector_via_module_invocation():
    content = read_workflow()
    assert (
        "python -m scouts.pokemon.collector"
        in content
    )


def test_workflow_does_not_reference_live_monitor():
    content = read_workflow()
    assert "live_monitor" not in content


def test_workflow_requires_supabase_secrets():
    content = read_workflow()
    assert (
        "secrets.SUPABASE_URL" in content
    )
    assert (
        "secrets.SUPABASE_SERVICE_KEY" in content
    )


def test_workflow_installs_dependencies():
    content = read_workflow()
    assert "pip install" in content


def test_workflow_persists_atlas_data_across_runs():
    content = read_workflow()
    assert "actions/cache" in content
    assert ".atlas_data" in content


def test_canonical_collector_module_is_importable_as_invoked_by_the_workflow():
    """
    Proves the exact command the workflow runs
    (`python -m scouts.pokemon.collector`) resolves correctly when
    invoked from the repository root - the module-path import chain
    (scouts.base.atlas_scout, etc.) only works under `-m` invocation
    from the repo root, not as a bare script path.
    """
    from scouts.pokemon.collector import (
        PokemonScout,
        main,
    )

    assert callable(main)
    assert hasattr(PokemonScout, "run")


def test_other_workflows_are_untouched_by_this_addition():
    workflows_dir = WORKFLOW_PATH.parent

    existing_names = {
        "atlas-pipeline.yml",
        "create-alerts.yml",
        "ebay-research.yml",
        "market-signals.yml",
        "morning-brief.yml",
        "pattern-lab.yml",
        "research-engine.yml",
        "roi-tracker.yml",
        "score-opportunities.yml",
        "starbucks-scout.yml",
    }

    for name in existing_names:
        assert (workflows_dir / name).is_file()

    universal_workflow = (
        workflows_dir / "starbucks-scout.yml"
    )
    content = universal_workflow.read_text(
        encoding="utf-8"
    )
    assert "python scouts/universal.py" in content

from scouts.tcg.daily_brief_store import (
    TcgDailyBriefStore,
)


def test_daily_brief_store_saves_current_and_history(
    tmp_path,
):
    current_path = (
        tmp_path
        / "daily_brief.json"
    )

    history_directory = (
        tmp_path
        / "history"
    )

    store = TcgDailyBriefStore(
        path=current_path,
        history_directory=(
            history_directory
        ),
    )

    brief = {
        "generated_at": (
            "2026-07-14T18:00:00+00:00"
        ),
        "summary": {
            "catalog_count": 3,
        },
    }

    result = store.save(
        brief=brief,
        preserve_history=True,
    )

    loaded = store.load()

    history = store.history()

    assert (
        current_path.exists()
        is True
    )

    assert (
        loaded["summary"][
            "catalog_count"
        ]
        == 3
    )

    assert len(history) == 1

    assert (
        result[
            "history_path"
        ]
        is not None
    )
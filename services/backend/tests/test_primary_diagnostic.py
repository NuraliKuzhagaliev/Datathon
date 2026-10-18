import pytest

from cashproof.media import Timeline
from diagnostic_clips import bounds, indices, select_rows, page
from diagnose_primary import question


def test_same_short_interval_supports_all_three_fps_without_truncation():
    timeline = Timeline([i / 30 for i in range(300)], 0, 10, 464, 848)
    start, end = bounds(5, timeline.duration)
    plans = [indices(timeline, start, end, fps) for fps in (1, 2, 4)]
    assert [len(plan) for plan in plans] == [5, 8, 15]
    assert all(plan[0] == plans[0][0] and plan[-1] == plans[0][-1] for plan in plans)
    with pytest.raises(ValueError):
        indices(timeline, 0, 14, 4)


@pytest.mark.parametrize("anchor", [0, 0.1, 5, 9.9, 10])
def test_edge_events_remain_inside_clamped_source_window(anchor):
    start, end = bounds(anchor, 10)
    assert 0 <= start <= anchor <= end <= 10 and end - start == 3.5


def test_selection_keeps_duplicate_annotations_and_never_selects_validation():
    manifest = {
        "related_groups_reviewed": True,
        "rows": [
            {"sha256": "a", "label": 1, "split": "development", "times_sec": [2]},
            {"sha256": "a", "label": 1, "split": "development", "times_sec": [4]},
            {"sha256": "b", "label": 0, "split": "development"},
            {"sha256": "c", "label": 1, "split": "validation"},
        ],
    }
    selected = select_rows(manifest, 1)
    assert len(selected) == 2 and len(selected[0]) == 2
    assert all(row["split"] == "development" for rows in selected for row in rows)


def test_visual_question_cannot_read_oracle_time_video_label_or_source_filename():
    prompt, schema = question(
        [
            {
                "id": "secret-source",
                "timestamp_sec": 123,
                "label": 1,
                "anchor_sec": 123,
                "path": "private-name.mov",
            }
        ]
    )
    assert (
        "secret-source" not in prompt
        and "123" not in prompt
        and "private-name" not in prompt
    )
    assert schema["properties"]["actions"]["items"]["properties"]["first_source_index"][
        "enum"
    ] == [0]


def test_private_review_page_resolves_frame_paths_and_escapes_names(tmp_path):
    result = page(
        {
            "diagnostic_id": "generated",
            "source_manifest_sha256": "0" * 64,
            "clips": [
                {
                    "id": "D001",
                    "source_name": "<script>injected</script>",
                    "source_path": str(tmp_path / "generated.mov"),
                    "source_label": 1,
                    "anchor_sec": 1.2,
                    "frames": {
                        "fps4-131k": [
                            {"path": "relative-generated.jpg", "timestamp_sec": 1.2}
                        ]
                    },
                }
            ],
        }
    )
    assert "<script>injected</script>" not in result
    assert "&lt;script&gt;injected&lt;/script&gt;" in result
    assert "connect-src 'none'" in result and 'src="file:' in result

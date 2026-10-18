import json
from evaluation_time_metrics import matches, score


def test_one_prediction_cannot_satisfy_both_distinct_annotations():
    assert matches([57, 68], [62], 10) == 1
    assert matches([57, 68], [57, 68], 2) == 2
    assert matches([0, 1], [1, 2], 1) == 2


def test_misses_and_failures_remain_in_timing_denominator(tmp_path):
    manifest = {
        "rows": [
            {"sha256": str(i), "label": 1, "split": "development", "times_sec": [5]}
            for i in range(3)
        ]
    }
    for i in range(3):
        case = tmp_path / str(i)
        case.mkdir()
        if i == 2:
            (case / "failure.json").write_text("{}")
        else:
            (case / "result.json").write_text(
                json.dumps(
                    {
                        "model_result": {
                            "violations": [{"timecode_sec": 6}] if i == 0 else []
                        }
                    }
                )
            )
    result = score(manifest, tmp_path, "development")
    assert result["annotated_instants_total"] == 3
    assert result["one_to_one_annotation_matches"]["within_2_sec"] == 1
    assert result["annotation_coverage"]["within_2_sec"] == 1 / 3
    assert result["positive_technical_failures"] == 1
    assert result["nearest_annotation_mae_denominator"] == 1
    assert not result["partial_evaluation"]


def test_missing_videos_are_explicitly_partial(tmp_path):
    manifest = {
        "rows": [
            {"sha256": str(i), "label": 1, "split": "development", "times_sec": [5]}
            for i in range(2)
        ]
    }
    case = tmp_path / "0"
    case.mkdir()
    (case / "failure.json").write_text("{}")
    result = score(manifest, tmp_path, "development")
    assert result["partial_evaluation"]
    assert result["expected_split_unique_videos"] == 2
    assert result["evaluated_unique_videos"] == 1
    assert result["missing_split_unique_videos"] == 1
    assert result["annotated_instants_total"] == 1

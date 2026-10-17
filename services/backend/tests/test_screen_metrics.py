import json

from evaluation_screen_metrics import score, proposals


def test_proposal_diagnostic_deduplicates_and_never_exposes_semantics(tmp_path):
    manifest = {
        "rows": [
            {
                "sha256": "positive",
                "label": 1,
                "split": "development",
                "times_sec": [57, 68],
            },
            {"sha256": "negative", "label": 0, "split": "development", "times_sec": []},
        ]
    }
    for case_name in ("positive", "negative"):
        private = tmp_path / case_name / "private-inference"
        private.mkdir(parents=True)
        for number, indices in enumerate(([0], [0], [999])):
            record = {
                "prompt": 'Source indices=[{"index":0,"seconds":62}] JSON={}',
                "output": json.dumps(
                    {
                        "visible_change": "PRIVATE_CAPTION_MUST_NOT_ESCAPE",
                        "observed": True,
                        "indices": indices,
                        "overflow": False,
                    }
                ),
            }
            (private / f"{number}.json").write_text(json.dumps(record))
        (private / "verification.json").write_text(
            json.dumps(
                {
                    "prompt": 'Candidate=generated. Source indices=[{"index":0,"source_seconds":57.0}] JSON={}',
                    "output": json.dumps(
                        {
                            "support": "unobservable",
                            "visible_change": "PRIVATE_CAPTION_MUST_NOT_ESCAPE",
                        }
                    ),
                }
            )
        )
    result = score(manifest, tmp_path, "development")
    assert result["unique_proposal_instants_on_positive_videos"] == 1
    assert result["one_to_one_proposal_matches"]["within_10_sec"] == 1
    assert result["proposal_annotation_coverage"]["within_10_sec"] == 0.5
    assert result["negative_videos_with_proposals"] == 1
    assert result["invalid_positive_proposal_records_excluded"] == 2
    assert result["verification_frame_annotation_availability"]["within_0.5_sec"] == 0.5
    assert "PRIVATE_CAPTION" not in json.dumps(result)


def test_joint_crop_views_use_real_source_times_and_do_not_duplicate_one_instant(
    tmp_path,
):
    private = tmp_path / "private-inference"
    private.mkdir()
    legend = [{"index": 0, "source_seconds": 1.2}, {"index": 1, "source_seconds": 1.2}]
    record = {
        "prompt": "Source indices=" + json.dumps(legend),
        "output": json.dumps(
            {
                "checks": {
                    "TEST-A": {
                        "events": [{"onset_index": 0}, {"onset_index": 1}],
                        "overflow": False,
                        "visible_change": "PRIVATE_CAPTION",
                    }
                }
            }
        ),
    }
    (private / "generated.json").write_text(json.dumps(record))
    times, invalid, _ = proposals(tmp_path)
    assert times == [1.2] and invalid == 0

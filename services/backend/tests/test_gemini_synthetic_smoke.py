from datetime import datetime, timedelta, timezone
import hashlib

import httpx
import pytest

from gemini_synthetic_smoke import SafeStop, api_json, validate_result, verify_free_tier
from gemini_synthetic_smoke import events_from_sides, generate_clip, ordered_frames
import copy
import json


@pytest.mark.parametrize(
    "change", ["paid", "key", "expired", "future", "budget", "unverified"]
)
def test_zero_spend_guard_rejects_unverified_project(change):
    now = datetime.now(timezone.utc)
    receipt = {
        "checked_at_utc": now.isoformat(),
        "billing_tier": "Free tier",
        "key_sha256": hashlib.sha256(b"test-key").hexdigest(),
        "verified_in_google_ai_studio": True,
        "max_spend_usd": 0,
    }
    verify_free_tier(receipt, "test-key", now)
    if change == "paid":
        receipt["billing_tier"] = "Tier 1"
    elif change == "key":
        receipt["key_sha256"] = "different"
    elif change == "expired":
        receipt["checked_at_utc"] = (now - timedelta(minutes=31)).isoformat()
    elif change == "future":
        receipt["checked_at_utc"] = (now + timedelta(minutes=1)).isoformat()
    elif change == "budget":
        receipt["max_spend_usd"] = 5
    else:
        receipt["verified_in_google_ai_studio"] = False
    with pytest.raises(SafeStop, match="ZERO_COST"):
        verify_free_tier(receipt, "test-key", now)


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_errors_never_retry_or_echo_provider_secrets(status):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status,
            json={"error": "test-secret"},
            headers={"location": "https://example.invalid"},
        )

    with httpx.Client(
        transport=httpx.MockTransport(respond), follow_redirects=False
    ) as client:
        with pytest.raises(SafeStop) as exc:
            api_json(client, "POST", "/models/test:generateContent", "test-secret", {})
    assert len(requests) == 1
    assert "test-secret" not in str(exc.value)
    assert "test-secret" not in str(requests[0].url)


@pytest.mark.parametrize(
    "text,finish",
    [
        ('{"event_times_sec":[-1],"direction_summary":"x"}', "STOP"),
        ('{"event_times_sec":[NaN],"direction_summary":"x"}', "STOP"),
        ('{"event_times_sec":[3,2],"direction_summary":"x"}', "STOP"),
        ('{"event_times_sec":[2,2],"direction_summary":"x"}', "STOP"),
        ('{"event_times_sec":[],"direction_summary":"x"}', "MAX_TOKENS"),
    ],
)
def test_incomplete_or_invalid_timestamps_are_failures(text, finish):
    body = {
        "candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}]
    }
    with pytest.raises(SafeStop):
        validate_result(body, 6)


def body_with_crossing():
    return {
        "event_times_sec": [3.0],
        "direction_summary": "left-to-right",
        "crossings": [
            {
                "before_time_sec": 2.75,
                "before_side": "left",
                "time_sec": 3.0,
                "after_time_sec": 3.25,
                "after_side": "right",
                "direction": "left_to_right",
            }
        ],
    }


def provider_body(value):
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": json.dumps(value)}]},
            }
        ]
    }


@pytest.mark.parametrize(
    "change",
    [
        "wrong_direction",
        "same_side",
        "event_not_selected",
        "backward_clock",
        "distant_witness",
        "boolean_time",
    ],
)
def test_inconsistent_visual_witnesses_fail_instead_of_becoming_negative(change):
    value = copy.deepcopy(body_with_crossing())
    crossing = value["crossings"][0]
    if change == "wrong_direction":
        crossing["direction"] = "right_to_left"
    elif change == "same_side":
        crossing["after_side"] = "left"
    elif change == "event_not_selected":
        value["event_times_sec"] = []
    elif change == "backward_clock":
        crossing["before_time_sec"] = 4.0
    elif change == "distant_witness":
        crossing["before_time_sec"] = 0.0
    else:
        crossing["time_sec"] = True
    with pytest.raises(SafeStop):
        validate_result(provider_body(value), 6, witnesses=True)


def test_reverse_crossing_is_preserved_but_never_counted_as_requested_event():
    value = body_with_crossing()
    crossing = value["crossings"][0]
    crossing.update(before_side="right", after_side="left", direction="right_to_left")
    value["event_times_sec"] = []
    assert validate_result(provider_body(value), 6, witnesses=True) == value


@pytest.mark.parametrize(
    "scenario",
    [
        "forward",
        "reverse",
        "repeated",
        "early",
        "late",
        "near_miss",
        "stationary_overlap",
        "near_line_start",
    ],
)
def test_actual_decoded_pts_and_pixel_truth_support_generated_events(
    tmp_path, scenario
):
    path = tmp_path / "synthetic.mp4"
    expected, _ = generate_clip(path, scenario)
    parts, frames = ordered_frames(path)
    value = {"frame_sides": [f["synthetic_expected_side"] for f in frames]}
    result = events_from_sides(value, frames)
    assert len(result["event_times_sec"]) == len(expected)
    assert all(abs(a - b) <= 0.11 for a, b in zip(result["event_times_sec"], expected))
    assert all(
        a["timestamp_sec"] < b["timestamp_sec"] for a, b in zip(frames, frames[1:])
    )
    assert len(parts) == len(frames) * 2
    assert all("synthetic_expected_side" not in json.dumps(p) for p in parts)


@pytest.mark.parametrize("sides", [["left"], ["left", "up"], ["left", True]])
def test_missing_or_invalid_frame_observations_fail(sides):
    frames = [
        {"frame_id": "f0", "timestamp_sec": 0},
        {"frame_id": "f1", "timestamp_sec": 0.3},
    ]
    with pytest.raises(SafeStop):
        events_from_sides({"frame_sides": sides}, frames)


def test_touching_line_then_returning_is_not_crossing():
    frames = [{"frame_id": f"f{i}", "timestamp_sec": i / 4} for i in range(4)]
    assert (
        events_from_sides({"frame_sides": ["left", "on", "on", "left"]}, frames)[
            "event_times_sec"
        ]
        == []
    )

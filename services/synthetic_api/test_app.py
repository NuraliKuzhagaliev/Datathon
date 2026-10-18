"""Offline tests: provider responses mocked; only generated public media used."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app as module  # noqa: E402


@pytest.fixture
def api(monkeypatch):
    app = importlib.reload(module)
    monkeypatch.setenv("SYNTHETIC_API_KEY", "test-only-laboratory-key")
    monkeypatch.delenv("GEMINI_LIVE_ENABLED", raising=False)
    with TestClient(app.app) as client:
        yield app, client


AUTH = {"X-API-Key": "test-only-laboratory-key"}


def wait(client, job_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        row = client.get(f"/api/synthetic/jobs/{job_id}", headers=AUTH).json()
        if row["status"] != "processing":
            return row
        time.sleep(0.02)
    pytest.fail("Synthetic processing timed out")


@pytest.mark.parametrize("scenario,expected", [
    ("near_line_start", [1.5]), ("forward", [3.0]), ("reverse", []),
    ("repeated", [2.0, 8.0]), ("early", [1.0]), ("late", [5.0]),
    ("near_miss", []), ("stationary_overlap", []),
])
def test_server_recomputes_all_eight_without_provider(api, monkeypatch, scenario, expected):
    app, client = api
    def forbidden(*args, **kwargs):
        pytest.fail("Recorded mode must not call Gemini")
    monkeypatch.setattr(app, "api_json", forbidden)
    response = client.post("/api/synthetic/jobs", json={"scenario": scenario}, headers=AUTH)
    assert response.status_code == 202
    row = wait(client, response.json()["job_id"])
    assert row["status"] == "done", row
    assert row["result"]["geometry_result"]["event_times_sec"] == expected
    assert row["result"]["new_gemini_requests"] == 0
    if scenario == "near_line_start":
        assert row["result"]["raw_gemini_result"]["event_times_sec"] == []


def test_auth_uploads_unknown_inputs_and_expiry(api):
    app, client = api
    for key in (None, "wrong"):
        headers = {} if key is None else {"X-API-Key": key}
        assert client.post("/api/synthetic/jobs", json={"scenario": "forward"}, headers=headers).status_code == 401
    assert client.post("/api/synthetic/jobs", json={"scenario": "../../private"}, headers=AUTH).status_code == 422
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "url": "https://example.com/video"}, headers=AUTH).status_code == 422
    assert client.post("/api/v1/analyze", json={}, headers=AUTH).status_code == 403
    assert client.post("/api/v1/analyze", files={"file": ("synthetic.mp4", b"fake")}, headers=AUTH).status_code == 415
    assert client.post("/api/synthetic/jobs", content=b"x"*1025, headers=AUTH).status_code == 413
    assert client.get("/api/synthetic/jobs/old-instance", headers=AUTH).status_code == 410
    assert client.get("/media/unknown.mp4").status_code == 404
    assert client.get("/health/ready").json()["jury_analysis_ready"] is False
    assert client.get("/api/synthetic/session").status_code == 401
    assert client.get("/api/synthetic/session", headers=AUTH).json()["synthetic_only"] is True
    assert client.get("/api/synthetic/health").json()["jury_analysis_ready"] is False


def enable(app, monkeypatch, age=0):
    key = "fake-provider-key"
    monkeypatch.setenv("GEMINI_API_KEY", key)
    monkeypatch.setenv("GEMINI_LIVE_ENABLED", "1")
    monkeypatch.setenv("GEMINI_FREE_TIER_RECEIPT", json.dumps({
        "checked_at_utc": (datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
        "billing_tier": "Free tier", "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "verified_in_google_ai_studio": True, "max_spend_usd": 0}))


def test_live_fails_closed_without_fresh_free_verification(api, monkeypatch):
    app, client = api
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH).status_code == 503
    enable(app, monkeypatch, age=1801)
    assert client.get("/health/ready").json()["gemini_live_ready"] is False
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH).status_code == 503
    assert app.LIVE_CALLS == 0


def test_live_provider_payload_and_separate_geometry(api, monkeypatch):
    app, client = api
    enable(app, monkeypatch)
    calls = []
    def provider(client, method, route, key, payload):
        calls.append(route)
        assert route == "/models/gemini-2.5-flash:generateContent"
        assert "expected" not in json.dumps(payload)
        assert "reference_event_times" not in json.dumps(payload)
        # Confidently wrong predictions must remain visible. Pixel measurements
        # are an independent synthetic baseline, not a claimed model correction.
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({"frame_sides": ['right'] * len(app.CATALOG['near_line_start']['frames'])})}]}}]}
    monkeypatch.setattr(app, "api_json", provider)
    response = client.post("/api/synthetic/jobs", json={"scenario": "near_line_start", "engine": "gemini"}, headers=AUTH)
    row = wait(client, response.json()["job_id"])
    assert row["status"] == "done", row
    assert row["result"]["new_gemini_requests"] == 1
    assert row["result"]["raw_gemini_result"]["event_times_sec"] == []
    assert row["result"]["geometry_result"]["event_times_sec"] == [1.5]
    assert len(row["result"]["geometry_observations"]) == len(app.CATALOG['near_line_start']['frames'])
    assert len(calls) == 1
    app.LIVE_CALLS = 8
    assert client.get("/health/ready").json()["gemini_live_ready"] is False


def test_quota_error_halts_without_retry_or_fake_negative(api, monkeypatch):
    app, client = api
    enable(app, monkeypatch)
    calls = []
    def provider(*args, **kwargs):
        calls.append(1)
        raise app.SafeStop("GEMINI_HTTP_429_NO_RETRY_OR_PAID_FALLBACK")
    monkeypatch.setattr(app, "api_json", provider)
    response = client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH)
    row = wait(client, response.json()["job_id"])
    assert row["status"] == "failed" and "result" not in row
    assert "429" in row["error"]["code"]
    assert app.HALTED and len(calls) == 1
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH).status_code == 503


def test_busy_and_public_console(api):
    app, client = api
    app.BUSY = True
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward"}, headers=AUTH).status_code == 429
    for route in ("/", "/console.js", "/console.css", "/media/forward.mp4"):
        assert client.get(route).status_code == 200
    response = client.get("/health/live")
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"


def test_zoom_input_and_model_selected_witnesses_are_not_pixel_answers(api, monkeypatch):
    app, client = api
    enable(app, monkeypatch)
    def provider(client, method, route, key, payload):
        assert 'crossings' in payload['generationConfig']['responseSchema']['properties']
        assert 'synthetic_expected_side' not in json.dumps(payload)
        assert 'reference_event_times_sec' not in json.dumps(payload)
        # Deliberately wrong model time must survive the independent geometry.
        rows = [{'before_frame_id':'f0003','before_side':'left','event_frame_id':'f0004',
                 'after_frame_id':'f0005','after_side':'right','direction':'left_to_right',
                 'observation':'Synthetic mocked observation'}]
        return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'crossings':rows})}]}}]}
    monkeypatch.setattr(app,'api_json',provider)
    response=client.post('/api/synthetic/jobs',json={'scenario':'forward','engine':'gemini','profile':'temporal-witness-v5'},headers=AUTH)
    row=wait(client,response.json()['job_id'])
    assert row['status']=='done', row
    assert row['result']['raw_gemini_result']['event_times_sec']==[2.0]
    assert row['result']['geometry_result']['event_times_sec']==[3.0]
    assert row['result']['prompt_version']=='temporal-witness-v5'
    frames=row['result']['frames']
    assert len(frames)==13 and frames[1]['timestamp_sec']==0.5 and frames[-1]['timestamp_sec']==5.9


@pytest.mark.parametrize('change', ['unknown_id','direction','wide_gap','duplicate','truncated'])
def test_witnesses_reject_unsupported_model_claims(api,change):
    from services.synthetic_api.observations import parse_witnesses
    app,_=api
    frames=[{'frame_id':f'f{i:04d}','timestamp_sec':i*.5} for i in range(8)]
    event={'before_frame_id':'f0001','before_side':'left','event_frame_id':'f0002',
           'after_frame_id':'f0003','after_side':'right','direction':'left_to_right','observation':'A crossing'}
    rows=[event]
    if change=='unknown_id':
        event['event_frame_id']='not-a-source-frame'
    if change=='direction':
        event['direction']='right_to_left'
    if change=='wide_gap':
        event['after_frame_id']='f0007'
    if change=='duplicate':
        rows.append(dict(event))
    body={'candidates':[{'finishReason':'MAX_TOKENS' if change=='truncated' else 'STOP','content':{'parts':[{'text':json.dumps({'crossings':rows})}]}}]}
    with pytest.raises(app.SafeStop):
        parse_witnesses(body,frames)


@pytest.mark.parametrize('profile',['native-video-v7','native-video-v8-high','native-video-v9-high'])
def test_native_video_preserves_model_timestamps_without_geometric_correction(api,monkeypatch,profile):
    app,client=api
    enable(app,monkeypatch)
    def provider(client,method,route,key,payload):
        part=payload['contents'][0]['parts'][0]
        assert part['inlineData']['mimeType']=='video/mp4' and part['videoMetadata']['fps']==4
        if profile in ('native-video-v8-high','native-video-v9-high'):
            assert payload['generationConfig']['mediaResolution']=='MEDIA_RESOLUTION_HIGH'
        result={'event_times_sec':[2.9],'direction_summary':'Model-selected time',
                'crossings':[{'before_time_sec':2.5,'before_side':'left','time_sec':2.9,
                              'after_time_sec':3.3,'after_side':'right','direction':'left_to_right'}]}
        return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(result)}]}}]}
    monkeypatch.setattr(app,'api_json',provider)
    response=client.post('/api/synthetic/jobs',json={'scenario':'forward','engine':'gemini','profile':profile},headers=AUTH)
    row=wait(client,response.json()['job_id'])
    assert row['status']=='done',row
    assert row['result']['raw_gemini_result']['event_times_sec']==[2.9]
    assert row['result']['geometry_result']['event_times_sec']==[3.0]


def test_invalid_model_output_is_failed_with_bounded_synthetic_diagnostic(api,monkeypatch):
    app,client=api
    enable(app,monkeypatch)
    text=json.dumps({'frame_sides':[]})
    monkeypatch.setattr(app,'api_json',lambda *args,**kwargs: {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':text}]}}]})
    response=client.post('/api/synthetic/jobs',json={'scenario':'forward','engine':'gemini'},headers=AUTH)
    row=wait(client,response.json()['job_id'])
    assert row['status']=='failed' and 'result' not in row
    assert row['model_diagnostic']=={'synthetic_only':True,'raw_model_text':text}
    assert 'fake-provider-key' not in json.dumps(row)
    assert app.HALTED


def test_reference_overlay_preserves_every_source_timestamp(api):
    import av
    import io
    from services.synthetic_api.observations import visible_reference_video
    app,_=api
    path=app.ASSETS/'near_line_start.mp4'
    video,meta=visible_reference_video(path)
    with av.open(str(path)) as source:
        original=[float(f.pts*f.time_base) for f in source.decode(video=0)]
    with av.open(io.BytesIO(video)) as processed:
        times=[float(f.pts*f.time_base) for f in processed.decode(video=0)]
    assert times==original and len(times)==60
    assert meta['method']=='static_red_reference_overlay'
    assert abs(meta['reference_x']-320)<=1


def test_crossing_projection_keeps_wire_output_and_never_changes_model_times(api):
    from services.synthetic_api.observations import parse_reference_output
    wire={'direction_summary':'A synthetic crossing','event_times_sec':[],
          'crossings':[{'before_time_sec':2.65,'before_side':'left','time_sec':2.9,
                        'after_time_sec':3.15,'after_side':'right','direction':'left_to_right'}]}
    body={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(wire)}]}}]}
    parsed=parse_reference_output(body,6)
    assert parsed['event_times_sec']==[2.9]
    assert parsed['wire_output']==wire and parsed['wire_output']['event_times_sec']==[]
    assert parsed['event_times_source']=='model_reported_crossings_only'


def test_new_model_requires_its_own_free_price_proof_not_only_project_tier(api,monkeypatch):
    app,client=api
    enable(app,monkeypatch)
    monkeypatch.setattr(app,'MODEL','gemini-3.8-flash')
    assert client.get('/health/ready').json()['gemini_live_ready'] is False

    proof={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'model':'gemini-3.8-flash',
           'currency':'USD','input_usd_per_million':0,'output_usd_per_million':0,
           'official_source':'https://ai.google.dev/gemini-api/docs/pricing',
           'verified_in_ai_studio':True,'key_sha256':hashlib.sha256(b'fake-provider-key').hexdigest()}
    monkeypatch.setenv('GEMINI_MODEL_PRICING_RECEIPT',json.dumps(proof))
    assert client.get('/health/ready').json()['gemini_live_ready'] is True
    proof['input_usd_per_million']=.75
    monkeypatch.setenv('GEMINI_MODEL_PRICING_RECEIPT',json.dumps(proof))
    assert client.get('/health/ready').json()['gemini_live_ready'] is False
    assert app.LIVE_CALLS==0
    proof['input_usd_per_million']=False
    monkeypatch.setenv('GEMINI_MODEL_PRICING_RECEIPT',json.dumps(proof))
    assert client.get('/health/ready').json()['gemini_live_ready'] is False


@pytest.mark.parametrize('observed_return',[True,False])
def test_temporal_review_uses_second_model_evidence_and_keeps_target_times(api,monkeypatch,observed_return):
    app,client=api
    enable(app,monkeypatch)
    calls=[]
    def crossing(t,direction):
        before,after=('left','right') if direction=='left_to_right' else ('right','left')
        return {'before_time_sec':t-.25,'before_side':before,'time_sec':t,
                'after_time_sec':t+.25,'after_side':after,'direction':direction}
    def provider(client,method,route,key,payload):
        calls.append(payload)
        app.LAST_CALL=0  # Mock provider consumes no actual time/quota.
        if len(calls)==1:
            rows=[crossing(2,'left_to_right'),crossing(8,'left_to_right')]
        else:
            assert 'BETWEEN' in payload['contents'][0]['parts'][-1]['text']
            rows=[crossing(5,'right_to_left')] if observed_return else []
        return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'direction_summary':'Synthetic model observation','crossings':rows})}]}}]}
    monkeypatch.setattr(app,'api_json',provider)
    response=client.post('/api/synthetic/jobs',json={'scenario':'repeated','engine':'gemini','profile':'native-reference-v12-review'},headers=AUTH)
    row=wait(client,response.json()['job_id'])
    assert len(calls)==2
    if observed_return:
        assert row['status']=='done',row
        result=row['result']
        assert result['new_gemini_requests']==2
        assert result['raw_gemini_result']['event_times_sec']==[2,8]
        assert [c['time_sec'] for c in result['raw_gemini_result']['crossings']]==[2,5,8]
        assert result['raw_gemini_result']['temporal_review']['target_times_unchanged'] is True
    else:
        assert row['status']=='failed' and 'result' not in row
        assert row['error']['code']=='MODEL_RETURN_PASS_NOT_VERIFIED'

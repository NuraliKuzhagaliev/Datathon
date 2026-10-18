"""Publish only regenerated synthetic inputs and whitelisted recorded observations."""
import argparse
import hashlib
import json
from pathlib import Path

from gemini_synthetic_smoke import generate_clip, events_from_sides
from synthetic_geometry import refine_ambiguous

REPO = Path(__file__).resolve().parents[1]
SOURCES = (
    'gemini-flash-sourceframes-v3-original-20261018-1',
    'gemini-flash-sourceframes-v3-challenge-20261018-1',
    'gemini-flash-sourceframes-v3-boundary-20261018-1',
)
TITLES = {
    'near_line_start': ('Старт рядом с линией', 'Start close to the line'),
    'forward': ('Пересечение слева направо', 'Left-to-right crossing'),
    'reverse': ('Обратное направление', 'Reverse direction'),
    'repeated': ('Повторные пересечения', 'Repeated crossings'),
    'early': ('Раннее событие', 'Early crossing'),
    'late': ('Позднее событие', 'Late crossing'),
    'near_miss': ('Движение без пересечения', 'Movement without crossing'),
    'stationary_overlap': ('Неподвижный объект у линии', 'Stationary object near the line'),
}


def export(recordings):
    public = REPO/'apps/web/public/synthetic-demo'
    public.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name in SOURCES:
        source = recordings/name
        report = json.loads((source/'aggregate.json').read_text())
        assert report['synthetic_only'] and report['private_videos_sent'] == 0
        for case in report['cases']:
            scenario = case['scenario']
            assert scenario in TITLES and scenario not in rows
            # Regenerate the video rather than publishing a supplied input file.
            video = public/f'{scenario}.mp4'
            expected, duration = generate_clip(video, scenario)
            assert hashlib.sha256(video.read_bytes()).hexdigest() == case['synthetic_video_sha256']
            frames = json.loads((source/f'synthetic-{scenario}-frames.json').read_text())
            frames = [{k: f[k] for k in ('frame_id','timestamp_sec')} for f in frames]
            sides = case['predicted']['frame_sides']
            assert len(sides) == len(frames) and all(s in ('left','on','right') for s in sides)
            refined, _ = refine_ambiguous(video, frames, sides)
            result = events_from_sides({'frame_sides':refined}, frames)
            rows[scenario] = {
                'id':scenario, 'title_ru':TITLES[scenario][0], 'title_en':TITLES[scenario][1],
                'video_url':f'/synthetic-demo/{scenario}.mp4', 'duration_sec':duration,
                'video_sha256':case['synthetic_video_sha256'], 'frames':frames,
                'recorded_at_utc':report['finished_at_utc'],
                'gemini_sides':sides, 'gemini_event_times_sec':case['predicted']['event_times_sec'],
                'reference_event_times_sec':expected,
                'recorded_hybrid_event_times_sec':result['event_times_sec'],
            }
    assert len(rows) == 8
    value = {
        'version':1, 'synthetic_only':True, 'mode':'recorded_gemini_and_live_browser_geometry',
        'model':'gemini-2.5-flash', 'prompt_version':'frame-sides-v3',
        'fresh_api_completed':3, 'fresh_api_planned':8, 'fresh_api_stop':'free_daily_quota_20_of_20',
        'full_replay_passed':8, 'full_replay_total':8,
        'cases':[rows[name] for name in TITLES],
    }
    (public/'recordings.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'exported_synthetic_cases':len(rows),'original_private_files_copied':0}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recordings-root',type=Path,required=True)
    export(parser.parse_args().recordings_root)

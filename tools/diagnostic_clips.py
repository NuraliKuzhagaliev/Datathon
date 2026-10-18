"""Private oracle-time development clips. Not an automatic detection benchmark."""

import argparse
import hashlib
import html
import json
from pathlib import Path
import time

from cashproof import media


SETTINGS = {
    "fps1-131k": {"fps": 1, "pixels": 131072, "image_tokens": 256},
    "fps2-131k": {"fps": 2, "pixels": 131072, "image_tokens": 256},
    "fps4-131k": {"fps": 4, "pixels": 131072, "image_tokens": 256},
    "fps2-source": {"fps": 2, "pixels": 393472, "image_tokens": 512},
}
ACTION_CODES = [
    "cash_handling",
    "object_handover",
    "walk_away",
    "document_handling",
    "bag_handling",
    "storage_transfer",
    "other_visible_action",
]


def bounds(anchor, duration, span=3.5):
    if not 0 <= anchor <= duration or duration <= 0 or span <= 0:
        raise ValueError("Invalid diagnostic interval")
    start = max(0.0, min(anchor - span / 2, duration - span))
    return start, min(duration, start + span)


def indices(timeline, start, end, fps):
    selected = media.sample_indices(timeline, start, end, fps)
    if len(selected) > 16:
        raise ValueError("Shorten the interval: diagnostic image count exceeds16")
    return selected


def select_rows(manifest, per_class):
    if per_class < 1 or not manifest.get("related_groups_reviewed"):
        raise ValueError(
            "Reviewed development grouping and positive sample size required"
        )
    groups = {}
    for row in manifest["rows"]:
        if row["split"] == "development":
            groups.setdefault(row["sha256"], []).append(row)
    selected, counts = [], {0: 0, 1: 0}
    for rows in groups.values():
        label = int(rows[0]["label"])
        if counts[label] >= per_class:
            continue
        if len({r["label"] for r in rows}) != 1:
            raise ValueError("Conflicting source labels")
        counts[label] += 1
        selected.append(rows)
    if min(counts.values()) != per_class:
        raise ValueError("Insufficient development examples")
    return selected


def page(manifest):
    cards = []
    options = '<option value="">Выберите наблюдаемое действие</option>' + "".join(
        f'<option value="{code}">{label}</option>'
        for code, label in zip(
            ACTION_CODES,
            [
                "Работа с наличными",
                "Передача предмета",
                "Уход от стойки",
                "Работа с документами",
                "Работа с сумкой",
                "Перемещение в хранилище",
                "Другое действие — уточните вопрос",
            ],
        )
    )
    for row in manifest["clips"]:
        thumbs = "".join(
            f'<figure><img loading="lazy" src="{html.escape(Path(f["path"]).resolve().as_uri(), quote=True)}"><figcaption>{f["timestamp_sec"]:.3f} с</figcaption></figure>'
            for f in row["frames"]["fps4-131k"]
        )
        cards.append(f'''<article data-id="{row["id"]}" data-anchor="{row["anchor_sec"]}"><h2>{row["id"]} · {html.escape(row["source_name"])}</h2>
        <p>Исходная метка видео: {row["source_label"]}. Ориентир: {row["anchor_sec"]:.3f} с — требует проверки человеком.</p>
        <video controls preload="metadata" src="{html.escape(Path(row["source_path"]).as_uri(), quote=True)}"></video><button data-jump>К ориентиру</button><button data-time>Взять текущее время</button>
        <div class="frames">{thumbs}</div><label>Какое действие проверить?<select data-code>{options}</select></label>
        <label>Один конкретный визуальный вопрос (без правового вывода)<textarea data-question maxlength="400" placeholder="Например: пересекает ли нарисованная фигура линию слева направо?"></textarea></label>
        <label>Это действие на фрагменте<select data-state><option value="pending">Не просмотрено</option><option value="present">Наблюдается</option><option value="absent">Отсутствует</option><option value="unobservable">Определить нельзя</option></select></label>
        <label>Первый подтверждаемый момент в исходном видео, секунды<input data-onset type="number" min="0" step="0.001" value="{row["anchor_sec"]}"></label>
        <label>Можно ли установить предполагаемое нарушение с доступным контекстом?<select data-legal><option value="pending">Не проверено</option><option value="yes">Да</option><option value="no">Нет, виден допустимый вариант</option><option value="unclear">Недостаточно сведений или видимости</option></select></label></article>''')
    meta = json.dumps(
        {
            "source_manifest_sha256": manifest["source_manifest_sha256"],
            "diagnostic_id": manifest["diagnostic_id"],
        }
    ).replace("<", "\\u003c")
    return """<!doctype html><html lang="ru"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src file:; media-src file:; connect-src 'none'"><title>CashProof · локальная диагностика</title>
    <style>body{font:16px system-ui;background:#111827;color:#eef2ff;max-width:1200px;margin:24px auto;padding:16px}article{border:1px solid #64748b;margin:24px 0;padding:20px;border-radius:12px}video{width:100%;max-height:480px;background:#000}label{display:block;margin:16px 0}textarea{width:95%;min-height:60px}button,select,input,textarea{font:inherit;padding:8px}.frames{display:flex;overflow:auto}figure{margin:8px;flex:0 0 170px}img{width:170px;object-fit:contain}header{position:sticky;top:0;background:#111827;padding:12px;z-index:1}</style>
    <header><h1>Проверка первичного просмотра</h1><p>Только development. Сначала отметьте собственное наблюдение, без ответов модели. Исходная метка «нарушение» не означает наличие любого выбранного действия: допустимый пересчёт тоже может содержать движение денег. Для отрицательного контроля отметьте фактическое отсутствие того же действия. Вопросы и описания остаются на компьютере; не отправляйте страницу или её скриншоты в чат.</p><button id="save">Сохранить диагностическую разметку JSON</button><span id="status"></span></header>CARDS
    <script type="application/json" id="meta">META</script><script>
    for(const card of document.querySelectorAll('article')){const video=card.querySelector('video');card.querySelector('[data-jump]').onclick=()=>{video.currentTime=Math.max(0,Number(card.dataset.anchor)-2);};card.querySelector('[data-time]').onclick=()=>{card.querySelector('[data-onset]').value=video.currentTime.toFixed(3);};}
    document.getElementById('save').onclick=()=>{const rows=[];for(const card of document.querySelectorAll('article')){const state=card.querySelector('[data-state]').value;if(state==='pending')continue;const question=card.querySelector('[data-question]').value.trim(),code=card.querySelector('[data-code]').value,legal=card.querySelector('[data-legal]').value,onset=Number(card.querySelector('[data-onset]').value);if(!question||!code||legal==='pending'||(state==='present'&&!Number.isFinite(onset))){document.getElementById('status').textContent=' Заполните вопрос, категорию и видимость для каждой просмотренной карточки.';return;}rows.push({clip_id:card.dataset.id,question,action_code:code,expected_action:state,event_time_sec:state==='present'?onset:null,violation_establishable:legal,human_reviewed:true});}if(!rows.length){document.getElementById('status').textContent=' Просмотрите хотя бы несколько положительных и отрицательных примеров.';return;}const result={...JSON.parse(document.getElementById('meta').textContent),human_reviewed:true,reviewed_at:new Date().toISOString(),rows};const u=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='diagnostic-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);document.getElementById('status').textContent=' Сохранён JSON. Сообщите только его локальный путь, без содержимого.';};</script></html>""".replace(
        "CARDS", "".join(cards)
    ).replace("META", meta)


def prepare(source_manifest, output, per_class=4):
    output = output.resolve()
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    selected = select_rows(source, per_class)
    output.mkdir(parents=True, exist_ok=False)
    clips = []
    for rows in selected:
        row = rows[0]
        path = Path(row["path"]).resolve()
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
                raise ValueError("Source integrity changed")
        timeline = media.decode_timeline(path, time.time() + 120)
        anchors = (
            sorted({float(t) for r in rows for t in r.get("times_sec", [])})
            if row["label"]
            else [timeline.duration / 2]
        )
        if not anchors:
            raise ValueError("Positive diagnostic needs an existing time annotation")
        for anchor in anchors:
            clip_id = f"D{len(clips) + 1:03d}"
            start, end = bounds(anchor, timeline.duration)
            plans = {
                name: indices(timeline, start, end, setting["fps"])
                for name, setting in SETTINGS.items()
            }
            frames = media.extract(
                path,
                timeline,
                sorted(set(i for plan in plans.values() for i in plan)),
                output / clip_id,
                time.time() + 120,
            )
            by_index = {frame["index"]: frame for frame in frames.values()}
            clips.append(
                {
                    "id": clip_id,
                    "source_path": str(path),
                    "source_sha256": row["sha256"],
                    "source_name": row["source_name"],
                    "source_label": int(row["label"]),
                    "split": "development",
                    "anchor_sec": anchor,
                    "anchor_human_verified": False,
                    "start_sec": start,
                    "end_sec": end,
                    "frames": {
                        name: [by_index[i] for i in plan]
                        for name, plan in plans.items()
                    },
                }
            )
    manifest = {
        "diagnostic_id": output.name,
        "oracle_time": True,
        "development_only": True,
        "source_manifest_sha256": hashlib.sha256(
            source_manifest.read_bytes()
        ).hexdigest(),
        "clips": clips,
        "settings": SETTINGS,
        "context_tokens": 6144,
        "meaning": "Provided positive times and midpoint negative snippets are diagnostic selection, not automatic localization or independent action ground truth.",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (output / "local-diagnostic-review.html").write_text(
        page(manifest), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "prepared": True,
                "development_unique": len(selected),
                "clips": len(clips),
                "max_images": max(
                    len(fs) for clip in clips for fs in clip["frames"].values()
                ),
                "validation_inputs": 0,
                "human_action_review_required": True,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-class", type=int, default=4)
    args = parser.parse_args()
    prepare(args.manifest, args.output, args.per_class)

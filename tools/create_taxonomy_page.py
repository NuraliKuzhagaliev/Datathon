"""Private human category review, development positives only; no cloud assets."""

import argparse
import hashlib
import html
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    registry = json.loads(args.rules.read_text(encoding="utf-8"))
    seen, rows = set(), []
    for row in manifest["rows"]:
        if (
            row["split"] == "development"
            and row["label"] == 1
            and row["sha256"] not in seen
        ):
            rows.append(row)
            seen.add(row["sha256"])
    guide, cards = [], []
    for rule in registry["rules"]:
        public = rule["public"]
        guide.append(
            "<li><b>"
            + html.escape(public["clause"] + ": " + public["display_name"])
            + "</b><br>"
            + html.escape(public["applicability"])
            + "<br>Исключения: "
            + html.escape("; ".join(public["exclusions"]))
            + "</li>"
        )
    for row in rows:
        checkboxes = "".join(
            '<label><input type="checkbox" value="'
            + html.escape(rule["public"]["rule_id"])
            + '"> '
            + html.escape(
                rule["public"]["clause"] + ": " + rule["public"]["display_name"]
            )
            + "</label>"
            for rule in registry["rules"]
        )
        cards.append(f'''<article data-hash="{row["sha256"]}"><h2>{html.escape(row["source_name"])}</h2>
        <video controls preload="none" src="{html.escape(Path(row["path"]).as_uri(), quote=True)}"></video>
        {checkboxes}<label>Другая наблюдаемая категория (если ни один пункт не подходит)<textarea data-other maxlength="500"></textarea></label>
        <label>Приватное уточнение видимости/контекста, без выводов о намерении<textarea data-note maxlength="500"></textarea></label>
        <label>Результат просмотра<select><option value="pending">Ещё не просмотрен</option><option value="reviewed">Просмотрен, категория выбрана</option><option value="uncertain">Просмотрен, определить нельзя</option></select></label></article>''')
    meta = {
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "registry_version": registry["version"],
    }
    data = json.dumps(meta).replace("<", "\\u003c")
    page = (
        """<!doctype html><html lang="ru"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; media-src file:; connect-src 'none'">
    <title>CashProof · приватная проверка категорий</title><style>body{font:16px system-ui;background:#111827;color:#eef2ff;margin:24px}p,details{max-width:1100px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:20px}article{border:1px solid #64748b;border-radius:12px;padding:16px}video{width:100%;height:260px;background:#000}label{display:block;margin:12px 0}textarea,select,button{font:inherit;padding:8px}textarea{display:block;box-sizing:border-box;width:100%;min-height:72px}li{margin:16px 0}header{position:sticky;top:0;background:#111827;padding:8px 0;z-index:2}</style>
    <header><h1>Приватная проверка категорий</h1><p>Только положительные примеры из части для разработки. Контрольные ролики сюда не включены. Просмотрите видео, отметьте подходящие наблюдаемые признаки либо укажите свою категорию локально. Если видимости недостаточно, выберите «определить нельзя». Метка из исходной таблицы не доказывает юридическое нарушение. Не отправляйте эту страницу, описания, кадры или скриншоты в облачный чат.</p><button id="save">Скачать приватный taxonomy-reviewed.json</button><span id="status"></span></header>
    <details><summary>Область применения и исключения проверенных правовых пунктов</summary><ul>GUIDE</ul></details><main>CARDS</main><script type="application/json" id="meta">META</script><script>
    document.getElementById('save').onclick=()=>{
      const rows=[]; const status=document.getElementById('status');
      for(const card of document.querySelectorAll('article')){
        const state=card.querySelector('select').value;
        const rules=[...card.querySelectorAll('input:checked')].map(e=>e.value);
        const other=card.querySelector('[data-other]').value.trim();
        if(state==='pending'||(state==='reviewed'&&!rules.length&&!other)){status.textContent=' Просмотрите все карточки и укажите категорию либо неопределённость.';return;}
        rows.push({sha256:card.dataset.hash,rule_ids:rules,other_category:other,note:card.querySelector('[data-note]').value.trim(),review_state:state});
      }
      const result={...JSON.parse(document.getElementById('meta').textContent),reviewed_at:new Date().toISOString(),development_only:true,taxonomy_reviewed:true,rows};
      const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
      const link=document.createElement('a');link.href=url;link.download='taxonomy-reviewed.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      status.textContent=' JSON скачан. Сообщите в чате только «готово» и путь к файлу; содержание не копируйте.';
    };</script></html>""".replace("GUIDE", "".join(guide))
        .replace("CARDS", "".join(cards))
        .replace("META", data)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print(
        json.dumps(
            {
                "created_private_taxonomy_page": True,
                "development_cards": len(rows),
                "validation_cards": 0,
            }
        )
    )


if __name__ == "__main__":
    main()

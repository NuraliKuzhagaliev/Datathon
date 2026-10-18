"""Create a private, self-contained local grouping page. Never open it in cloud UI QA."""

import argparse
from collections import defaultdict
import html
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for row in manifest["rows"]:
        groups[row["sha256"]].append(row)
    cards = []
    for digest, rows in groups.items():
        row = rows[0]
        names = " / ".join(r["source_name"] for r in rows)
        options = "".join(
            f'<option value="{v}"'
            + (" selected" if row["split"] == v else "")
            + f">{v}</option>"
            for v in ["development", "validation"]
        )
        cards.append(f'''<article data-hash="{digest}"><h2>{html.escape(names)}</h2>
        <video controls preload="none" src="{html.escape(Path(row["path"]).as_uri(), quote=True)}"></video>
        <label>Related-take group <input data-group value="{html.escape(row["group"], quote=True)}"></label>
        <label>Split <select data-split>{options}</select></label><small>Duplicate label rows: {len(rows)}. Keep them together.</small></article>''')
    data = (
        json.dumps(manifest, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; media-src file:; connect-src 'none'">
    <title>Private CashProof dataset grouping</title><style>body{font:16px system-ui;background:#111827;color:#f3f4f6;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}article{border:1px solid #4b5563;border-radius:10px;padding:16px}h2{font-size:16px}video{width:100%;height:280px;background:#000}label,small{display:block;margin-top:12px}input,select,button{font:inherit;padding:8px;max-width:95%}header{position:sticky;top:0;background:#111827;padding:12px 0}p{max-width:1000px}</style>
    <header><h1>Private local review · related-take grouping</h1><p>Open locally with network disconnected if preferred. Do not share screenshots, frames, descriptions or this page with cloud AI. Assign the same group to related takes/scenes. Exact duplicates are already one card. Keep each group in one split. Establish grouping before freezing the split; use development clips for taxonomy/tuning. No accuracy has been measured by this page.</p>
    <label><input type="checkbox" id="reviewed"> I reviewed related takes locally and kept their groups together.</label><button id="save">Download private reviewed manifest</button><span id="status"></span></header><main>CARDS</main><script type="application/json" id="data">DATA</script><script>
    const source=JSON.parse(document.getElementById('data').textContent);
    document.getElementById('save').onclick=()=>{
      const status=document.getElementById('status');
      if(!document.getElementById('reviewed').checked){status.textContent=' Complete local review first.';return;}
      const choices=new Map();const splits=new Map();
      for(const card of document.querySelectorAll('article')){
        const group=card.querySelector('[data-group]').value.trim();const split=card.querySelector('[data-split]').value;
        if(!group){status.textContent=' Every group needs an ID.';return;}
        if(splits.has(group)&&splits.get(group)!==split){status.textContent=' A related group crosses splits.';return;}
        splits.set(group,split);choices.set(card.dataset.hash,{group,split});
      }
      const output={...source,related_groups_reviewed:true,split_status:'Locally reviewed; freeze before validation',rows:source.rows.map(r=>({...r,...choices.get(r.sha256)}))};
      const blob=new Blob([JSON.stringify(output,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);
      const link=document.createElement('a');link.href=url;link.download='evaluation-manifest.reviewed.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      status.textContent=' Save the downloaded JSON as private-data/evaluation-manifest.json. Do not return case observations to the coding chat.';
    };</script></html>""".replace("CARDS", "".join(cards)).replace("DATA", data)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(page, encoding="utf-8")
    print(
        json.dumps(
            {
                "created_private_review_page": True,
                "unique_cards": len(groups),
                "human_review_required": True,
            }
        )
    )


if __name__ == "__main__":
    main()

"""Private metadata/label preparation. No video pixels or observations are exposed."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import unicodedata
from zipfile import ZipFile
import xml.etree.ElementTree as E


def sheet_rows(path):
    with ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = [
                "".join(t.text or "" for t in s.findall(".//{*}t"))
                for s in E.fromstring(z.read("xl/sharedStrings.xml"))
            ]
        root = E.fromstring(z.read("xl/worksheets/sheet1.xml"))
        for row in root.findall(".//{*}row"):
            values = []
            for c in row.findall("{*}c"):
                column = re.match(r"[A-Z]+", c.attrib.get("r", "A"))[0]
                index = 0
                for letter in column:
                    index = index * 26 + ord(letter) - 64
                while len(values) < index:
                    values.append("")
                text = c.findtext("{*}v", "")
                if c.attrib.get("t") == "s":
                    text = strings[int(text)]
                elif c.attrib.get("t") == "inlineStr":
                    text = "".join(t.text or "" for t in c.findall(".//{*}t"))
                values[index - 1] = text
            yield values


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    videos = list(a.dataset.rglob("*.MOV")) + list(a.dataset.rglob("*.mov"))
    videos = list({f.resolve() for f in videos})
    sheets = list(a.dataset.rglob("*.xlsx"))
    if len(sheets) != 1:
        raise ValueError("Expected exactly one label workbook")
    by_name = {f.stem: f for f in videos}
    hashes = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in videos}
    rows = []
    canonical = {}
    for values in sheet_rows(sheets[0]):
        if len(values) < 3:
            continue
        name = Path(values[0]).stem
        if name not in by_name:
            continue  # header only; final count check rejects missing labels
        source = by_name[name]
        label = values[2].strip().lower()
        binary = (
            0
            if label in {"нет нарушения", "без нарушения", "no_violation", "0"}
            else 1
            if label in {"нарушение", "violation", "1"}
            else None
        )
        if binary is None:
            raise ValueError("Unexpected binary label")
        value = values[1].strip()
        seconds = []
        if value and value not in {"-", "—", "0"}:
            if ":" in value:
                parts = [float(v.replace(",", ".")) for v in value.split(":")]
                seconds = [sum(v * 60**i for i, v in enumerate(reversed(parts)))]
            else:
                minute = re.fullmatch(
                    r"(\d+)\s*минут[аы]?\s*(\d+(?:[.,]\d+)?)\s*секунд[аы]?", value, re.I
                )
                if minute:
                    seconds = [
                        float(minute[1]) * 60 + float(minute[2].replace(",", "."))
                    ]
                    match = True
                else:
                    match = re.fullmatch(
                        r"(\d+(?:[.,]\d+)?)\s*(?:секунда|секунды|секунд|сек\.?|с\.?)?",
                        value,
                        re.I,
                    )
                if not match:
                    raise ValueError("Unrecognized timestamp format; inspect privately")
                if not minute:
                    seconds = [float(match[1].replace(",", "."))]
        identity = unicodedata.normalize("NFC", name).upper().replace("Х", "X")
        digits = re.search(r"X[-_ ]*(\d+)", identity)
        identity = f"X-{int(digits[1]):02d}" if digits else identity
        if identity in canonical and canonical[identity] != source:
            raise ValueError("Canonical ID collision")
        canonical[identity] = source
        rows.append(
            dict(
                path=str(source),
                source_name=source.name,
                canonical_id=identity,
                label=binary,
                times_sec=seconds,
                sha256=hashes[source],
                group=hashes[source],
                split="development",
            )
        )
    if len(rows) != len(videos):
        raise ValueError("Label/video count mismatch")
    groups = defaultdict(list)
    for row in rows:
        groups[row["sha256"]].append(row)
    # Provisional stratification. A local reviewer must join related takes BEFORE locking.
    rng = random.Random(20261017)
    for label in [0, 1]:
        selected = [g for g, rs in groups.items() if rs[0]["label"] == label]
        rng.shuffle(selected)
        for digest in selected[:6]:
            for row in groups[digest]:
                row["split"] = "validation"
    out = {
        "related_groups_reviewed": False,
        "split_status": "PROVISIONAL: local related-take review required",
        "rows": rows,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "videos": len(videos),
                "label_rows": len(rows),
                "unique_hashes": len(groups),
                "positive_rows": sum(r["label"] for r in rows),
                "negative_rows": sum(1 - r["label"] for r in rows),
                "duplicate_groups": sum(len(rs) > 1 for rs in groups.values()),
                "related_groups_reviewed": False,
            }
        )
    )


if __name__ == "__main__":
    main()

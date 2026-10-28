"""File parsing and export: CSV/JSON in, output.csv out.

Structure only. Turning text into facts belongs to the engine (arena/extract.py).
"""
import csv
import io
import json
import math
import os

INPUT_COLUMNS = ("id", "text", "date", "label")
OUTPUT_COLUMNS = ("id", "type", "text", "form", "label", "confidence")
LABELS = ("true", "false", "unsure")


class InputError(ValueError):
    """The input file does not have the shape the contract gives it."""


def _sniff_delimiter(first_line):
    return ";" if first_line.count(";") > first_line.count(",") else ","


def parse_rows(data, require_form=False):
    """Parse CSV text into row dicts with id, text, date, label (and form if present).

    Accepts a BOM, CRLF, quoted cells with commas and line breaks, and the
    semicolon CSV Excel writes with a Romanian locale.
    """
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise InputError(f"not UTF-8: {e}") from None
    data = data.lstrip("﻿")
    if not data.strip():
        raise InputError("empty file")
    delimiter = _sniff_delimiter(data.split("\n", 1)[0])
    reader = csv.DictReader(io.StringIO(data, newline=""), delimiter=delimiter)
    columns = {(c or "").strip().lower(): c for c in reader.fieldnames or []}
    needed = INPUT_COLUMNS + (("form",) if require_form else ())
    missing = [c for c in needed if c not in columns]
    if missing:
        raise InputError(f"missing columns: {', '.join(missing)}")
    rows, seen = [], set()
    for n, raw in enumerate(reader, start=2):
        if None in raw:
            raise InputError(f"line {n}: more cells than columns")
        row = {c: (raw.get(columns[c]) or "").strip() for c in INPUT_COLUMNS}
        if "form" in columns:
            row["form"] = raw.get(columns["form"]) or ""
        row["label"] = row["label"].lower()
        if not row["id"]:
            raise InputError(f"line {n}: empty id")
        if row["id"] in seen:
            raise InputError(f"line {n}: duplicate id {row['id']!r}")
        if row["label"] and row["label"] not in LABELS:
            raise InputError(f"line {n}: label {row['label']!r} is not true, false or unsure")
        seen.add(row["id"])
        rows.append(row)
    return rows


def read_rows(path, require_form=False):
    with open(path, "rb") as f:
        return parse_rows(f.read(), require_form=require_form)


def read_lexicon(path):
    with open(path, encoding="utf-8-sig") as f:
        lexicon = json.load(f)
    if not isinstance(lexicon, dict) or "subjects" not in lexicon:
        raise InputError("lexicon.json has no subjects")
    lexicon.setdefault("events", [])
    return lexicon


def split_rows(rows):
    """(labelled, unlabelled) in input order."""
    return [r for r in rows if r["label"]], [r for r in rows if not r["label"]]


def _confidence_cell(label, confidence):
    if label == "unsure" or confidence is None:
        return ""
    c = float(confidence)
    if math.isnan(c):
        return ""
    return f"{min(1.0, max(0.5, c)):.3f}".rstrip("0").rstrip(".")


def output_rows(predictions, claims):
    """The six official columns, predictions first, then claims in order."""
    out, seen = [], set()
    for p in predictions:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        label = p.get("label") or "unsure"
        conf = _confidence_cell(label, p.get("confidence"))
        if label != "unsure" and not conf:
            label = "unsure"
        out.append({"id": p["id"], "type": "", "text": "", "form": "", "label": label, "confidence": conf})
    for c in claims:
        form = c["form"] if isinstance(c["form"], str) else json.dumps(c["form"], ensure_ascii=False, separators=(",", ":"))
        out.append({"id": c["id"], "type": c["type"], "text": c["text"], "form": form,
                    "label": "true", "confidence": _confidence_cell("true", c.get("confidence", 0.5)) or "0.5"})
    return out


def write_output(predictions, claims, output_path):
    """Write output.csv atomically: a temp file in the same directory, then rename."""
    directory = os.path.dirname(os.path.abspath(output_path))
    tmp = os.path.join(directory, f".{os.path.basename(output_path)}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(output_rows(predictions, claims))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, output_path)

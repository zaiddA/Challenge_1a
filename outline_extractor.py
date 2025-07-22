#!/usr/bin/env python3
import os
import re
import json
import fitz  # PyMuPDF
import numpy as np
from collections import Counter

def detect_title(doc):
    """
    Attempt to get title from PDF metadata; if unavailable or too short,
    fall back to the largest-font span on page 1.
    """
    meta = doc.metadata.get("title", "")
    if meta and len(meta.strip()) > 5:
        return meta.strip()
    return detect_title_by_font(doc)

def detect_title_by_font(doc):
    """
    On page 1, find spans ≥ 3 words with the largest font size.
    If multiple, choose the one highest on the page.
    """
    page = doc[0]
    blocks = page.get_text("dict")["blocks"]
    max_size = 0
    candidates = []

    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for sp in line["spans"]:
                text = sp["text"].strip()
                size = round(sp["size"], 1)
                if len(text.split()) < 3:
                    continue
                if size > max_size:
                    max_size = size
                    candidates = [(text, sp["bbox"][1])]
                elif size == max_size:
                    candidates.append((text, sp["bbox"][1]))

    if not candidates:
        return ""  # fallback empty
    # pick the candidate with the smallest y-coordinate (highest on page)
    title = sorted(candidates, key=lambda x: x[1])[0][0]
    return title

def compute_body_font_size(doc):
    """
    Compute the most common font size (mode) across all text spans —
    assumed to be the body text size.
    """
    sizes = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                for sp in line["spans"]:
                    sizes.append(round(sp["size"], 1))
    if not sizes:
        return 0
    counts = Counter(sizes)
    return counts.most_common(1)[0][0]

def thresholds(body_size):
    """
    Define heading thresholds relative to the body font size.
    Adjust these offsets as needed for your PDF collection.
    """
    return {
        "H1": body_size + 3.0,
        "H2": body_size + 1.5
    }

def assign_level(span, thr):
    """
    Assign H1/H2/H3 based on:
      1) absolute font-size thresholds
      2) numbering patterns (e.g. "1.1.2" -> H3)
      3) bold + low indent heuristics
    """
    text = span["text"]
    size = span["size"]
    bold = span["bold"]
    indent = span["indent"]

    # 1) size-based
    if thr["H1"] and size >= thr["H1"]:
        return "H1"
    if thr["H2"] and size >= thr["H2"]:
        return "H2"

    # 2) numbering pattern (depth -> level)
    num = re.match(r"^(\d+(\.\d+)+)\s+", text)
    if num:
        depth = num.group(1).count(".")
        return {0: "H1", 1: "H2", 2: "H3"}.get(depth, "H3")

    # 3) bold vs indent heuristics
    if bold and indent < 100:
        return "H2"
    if bold:
        return "H3"

    return None

def detect_headings(doc, body_size):
    """
    Walk through each span in page order, classify as heading or not,
    and collect level, text, and page number.
    """
    thr = thresholds(body_size)
    outline = []

    for pno, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        # quick skip if page has no large fonts
        # (optional optimization)
        page_sizes = [round(sp["spans"][0]["size"],1)
                      for b in blocks if b["type"]==0
                      for sp in b["lines"]]
        if page_sizes and max(page_sizes) < thr.get("H2", 0):
            continue

        for b in blocks:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                for sp in line["spans"]:
                    text = sp["text"].strip()
                    if not text:
                        continue
                    span = {
                        "text": text,
                        "size": round(sp["size"], 1),
                        "bold": bool(sp.get("flags", 0) & 2),
                        "indent": sp["bbox"][0]
                    }
                    # skip very short noise
                    if len(text) < 4:
                        continue
                    lvl = assign_level(span, thr)
                    if lvl:
                        outline.append({
                            "level": lvl,
                            "text": text,
                            "page": pno
                        })
    return outline

def extract_outline(pdf_path):
    """
    Full pipeline for a single PDF: load, detect title, body size,
    headings, then return dict.
    """
    doc = fitz.open(pdf_path)
    title = detect_title(doc)
    body_size = compute_body_font_size(doc)
    headings = detect_headings(doc, body_size)
    doc.close()
    return {"title": title, "outline": headings}

def main():
    inp_dir = "/app/input"
    out_dir = "/app/output"
    os.makedirs(out_dir, exist_ok=True)

    for fname in os.listdir(inp_dir):
        if not fname.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(inp_dir, fname)
        result = extract_outline(pdf_path)
        json_name = fname[:-4] + ".json"
        out_path = os.path.join(out_dir, json_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Processed {fname} → {json_name}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import re
import json
import argparse
import fitz  # PyMuPDF
from collections import Counter

def detect_title(doc):
    """
    Get title from metadata or fall back to the largest-font span on page 1.
    """
    meta = doc.metadata.get("title", "")
    if meta and len(meta.strip()) > 5:
        return meta.strip()
    return detect_title_by_font(doc)

def detect_title_by_font(doc):
    """
    On page 1, find spans ≥3 words with the largest font size.
    If multiple, pick the highest (smallest y).
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
        return ""
    # pick the topmost candidate
    title = sorted(candidates, key=lambda x: x[1])[0][0]
    return title

def compute_body_font_size(doc):
    """
    Compute mode of all font sizes across the document (assumed body size).
    """
    sizes = []
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                for sp in line["spans"]:
                    sizes.append(round(sp["size"], 1))
    if not sizes:
        return 0
    return Counter(sizes).most_common(1)[0][0]

def thresholds(body_size):
    """
    Heading size thresholds relative to body font size.
    """
    return {
        "H1": body_size + 3.0,
        "H2": body_size + 1.5
    }

def assign_level(span, thr):
    """
    Determine heading level for a span using size, numbering, and bold/indent heuristics.
    """
    text = span["text"]
    size = span["size"]
    bold = span["bold"]
    indent = span["indent"]

    # 1) Size-based
    if thr["H1"] and size >= thr["H1"]:
        return "H1"
    if thr["H2"] and size >= thr["H2"]:
        return "H2"

    # 2) Numbering pattern
    m = re.match(r"^(\d+(\.\d+)+)\s+", text)
    if m:
        depth = m.group(1).count(".")
        return {0: "H1", 1: "H2", 2: "H3"}.get(depth, "H3")

    # 3) Bold/indent heuristics
    if bold and indent < 100:
        return "H2"
    if bold:
        return "H3"

    return None

def detect_headings(doc, body_size):
    """
    Scan every text span in page order and collect headings.
    """
    thr = thresholds(body_size)
    outline = []

    for pno, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        # optional skip: if no span exceeds H2 threshold, skip page
        sizes = [round(sp["size"],1)
                 for b in blocks if b["type"]==0
                 for line in b["lines"] for sp in line["spans"]]
        if sizes and max(sizes) < thr["H2"]:
            continue

        for b in blocks:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                for sp in line["spans"]:
                    text = sp["text"].strip()
                    if not text or len(text) < 4:
                        continue
                    span = {
                        "text": text,
                        "size": round(sp["size"], 1),
                        "bold": bool(sp.get("flags", 0) & 2),
                        "indent": sp["bbox"][0]
                    }
                    lvl = assign_level(span, thr)
                    if lvl:
                        outline.append({"level": lvl, "text": text, "page": pno})
    return outline

def extract_outline(pdf_path):
    """
    Full pipeline: open PDF, detect title, body size, headings, return dict.
    """
    doc = fitz.open(pdf_path)
    title = detect_title(doc)
    body_size = compute_body_font_size(doc)
    headings = detect_headings(doc, body_size)
    doc.close()
    return {"title": title, "outline": headings}

def main():
    parser = argparse.ArgumentParser(description="PDF Outline Extractor")
    parser.add_argument(
        "-i", "--input-dir",
        default="input",
        help="Folder containing PDFs (default: ./input)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="output",
        help="Folder to write JSON files (default: ./output)"
    )
    parser.add_argument(
        "-f", "--file",
        help="(Optional) Specific PDF filename to process"
    )
    args = parser.parse_args()

    inp_dir = args.input_dir
    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    for fname in os.listdir(inp_dir):
        if not fname.lower().endswith(".pdf"):
            continue
        if args.file and fname != args.file:
            continue

        pdf_path = os.path.join(inp_dir, fname)
        result = extract_outline(pdf_path)

        out_name = fname[:-4] + ".json"
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"→ {fname}  →  {out_name}")

if __name__ == "__main__":
    main()

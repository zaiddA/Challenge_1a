#!/usr/bin/env python3
import os
import re
import json
import argparse
import base64
import fitz                        # PyMuPDF
from PIL import Image, ImageFilter, ImageEnhance
from collections import Counter
import pytesseract                # Tesseract OCR wrapper
from langdetect import detect     # optional language detection

# ─── CONFIGURABLE BLACKLIST & DUPLICATE FILTER ───────────────────────────────

BLACKLIST = {
    "table of contents", "acknowledgements", "revision history",
    "copyright notice", "version 1.0", "copyright © international software testing qualifications board"
}

def is_boilerplate(text):
    txt = re.sub(r"\s+", " ", text.strip().lower())
    return any(txt.startswith(bl) for bl in BLACKLIST)

# ─── TITLE DETECTION ──────────────────────────────────────────────────────────

def detect_title(doc):
    meta = doc.metadata.get("title", "")
    if meta and len(meta.strip()) > 5 and not is_boilerplate(meta):
        return meta.strip()
    return detect_title_by_font(doc)

def detect_title_by_font(doc):
    page = doc[0]
    spans = [
        (round(sp["size"],1), sp["text"].strip(), sp["bbox"][1])
        for b in page.get_text("dict")["blocks"] if b["type"]==0
        for line in b["lines"] for sp in line["spans"]
        if len(sp["text"].split()) >= 3
    ]
    if not spans:
        return ""
    # pick largest size, then topmost
    max_size = max(s for s,_,_ in spans)
    candidates = [(t,y) for s,t,y in spans if s==max_size]
    return sorted(candidates, key=lambda x: x[1])[0][0]

# ─── BODY FONT SIZE ESTIMATION ────────────────────────────────────────────────

def compute_body_font_size(doc):
    sizes = [ round(sp["size"],1)
        for page in doc
        for b in page.get_text("dict")["blocks"] if b["type"]==0
        for line in b["lines"] for sp in line["spans"]
    ]
    if not sizes:
        return 0
    return Counter(sizes).most_common(1)[0][0]

# ─── HEADING DETECTION ────────────────────────────────────────────────────────

def thresholds(body_size):
    # bump thresholds slightly to cut false positives
    return {"H1": body_size + 4.0, "H2": body_size + 2.0}

def assign_level(span, thr):
    text, size, bold, indent = span["text"], span["size"], span["bold"], span["indent"]
    # skip boilerplate or too-short
    if is_boilerplate(text) or len(text) < 4:
        return None
    # size rules
    if size >= thr["H1"]:
        return "H1"
    if size >= thr["H2"]:
        return "H2"
    # numbering patterns
    m = re.match(r"^(\d+(\.\d+)+)\s+", text)
    if m:
        depth = m.group(1).count(".")
        return {0:"H1",1:"H2",2:"H3"}.get(depth, "H3")
    # bold/indent heuristics
    if bold and indent < 100:
        return "H2"
    if bold:
        return "H3"
    return None

def detect_headings(doc, body_size):
    thr = thresholds(body_size)
    outline = []
    seen_texts = set()
    last_text = None

    for pno, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        # skip pages with no candidate sizes
        sizes = [ round(sp["size"],1)
            for b in blocks if b["type"]==0
            for line in b["lines"] for sp in line["spans"]
        ]
        if not sizes or max(sizes) < thr["H2"]:
            continue

        for b in blocks:
            if b["type"] != 0: continue
            for line in b["lines"]:
                for sp in line["spans"]:
                    text = sp["text"].strip()
                    span = {
                        "text": text,
                        "size": round(sp["size"],1),
                        "bold": bool(sp.get("flags",0)&2),
                        "indent": sp["bbox"][0]
                    }
                    lvl = assign_level(span, thr)
                    if not lvl:
                        continue
                    # collapse consecutive duplicates
                    key = (lvl, text.lower())
                    if text == last_text or key in seen_texts:
                        continue
                    outline.append({"level": lvl, "text": text, "page": pno})
                    seen_texts.add(key)
                    last_text = text
    return outline

# ─── MAIN PIPELINE & BONUS FEATURES ──────────────────────────────────────────

def extract_outline(pdf_path):
    doc = fitz.open(pdf_path)
    title = detect_title(doc)
    body_size = compute_body_font_size(doc)
    headings = detect_headings(doc, body_size)

    # OCR fallback for pages with no headings
    if not headings:
        for pno in range(1, doc.page_count+1):
            text = doc[pno-1].get_text().strip()
            if not text:
                pix = doc[pno-1].get_pixmap(matrix=fitz.Matrix(2,2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_txt = pytesseract.image_to_string(img, lang="eng+jpn+spa")
                snippet = ocr_txt.strip().split("\n")[0]
                if snippet and not is_boilerplate(snippet):
                    headings.append({"level":"H1", "text": snippet, "page": pno})

    doc.close()
    return {"title": title, "outline": headings}

def main():
    parser = argparse.ArgumentParser(description="PDF Outline Extractor (tuned)")
    parser.add_argument("-i","--input-dir", default="input")
    parser.add_argument("-o","--output-dir", default="output")
    parser.add_argument("-f","--file", help="process only this PDF")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    stats = {
        "num_docs":0,
        "heading_counts":{"H1":0,"H2":0,"H3":0},
        "pages_no_heading":[],
        "languages":{}
    }
    previews = {}
    thumb_dir = os.path.join(args.output_dir, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)

    for fname in sorted(os.listdir(args.input_dir)):
        if not fname.lower().endswith(".pdf"): continue
        if args.file and fname != args.file: continue

        path = os.path.join(args.input_dir, fname)
        result = extract_outline(path)

        # write outline JSON
        out_json = os.path.join(args.output_dir, fname[:-4]+".json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # detect language from first heading
        snippet = result["outline"][0]["text"] if result["outline"] else ""
        stats["languages"][fname] = detect(snippet) if snippet else "unknown"
        stats["num_docs"] += 1

        previews[fname] = []
        doc = fitz.open(path)
        total_pages = doc.page_count
        pages_with_h = set()

        for h in result["outline"]:
            lvl, txt, pno = h["level"], h["text"], h["page"]
            stats["heading_counts"][lvl] += 1
            pages_with_h.add(pno)

            # render thumbnail
            page = doc[pno-1]
            pix = page.get_pixmap(matrix=fitz.Matrix(0.2,0.2))
            thumb = os.path.join(thumb_dir, f"{fname}_p{pno}.png")
            pix.save(thumb)

            # enhance thumbnail
            img = Image.open(thumb)
            w,h = img.size
            img = img.resize((w*2,h*2), Image.LANCZOS)
            img = img.filter(ImageFilter.UnsharpMask(2,150,3))
            img = ImageEnhance.Contrast(img).enhance(1.2)
            img = ImageEnhance.Sharpness(img).enhance(1.3)
            img.save(thumb, optimize=True)

            previews[fname].append((lvl, txt, pno, thumb))

        # record pages with no headings
        no_h = [p for p in range(1,total_pages+1) if p not in pages_with_h]
        if no_h:
            stats["pages_no_heading"].append({"doc":fname, "pages":no_h})
        doc.close()

    # finalize stats
    total_h = sum(stats["heading_counts"].values())
    stats["avg_headings_per_doc"] = round(total_h / stats["num_docs"], 2)
    with open(os.path.join(args.output_dir,"stats.json"),"w",encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # generate HTML preview
    html = [
        "<html><head><style>",
        "ul{list-style:none;} .toggle{cursor:pointer;}</style>",
        "<script>function toggle(el){let d=el.nextElementSibling; d.style.display=d.style.display=='none'?'block':'none';}</script>",
        "</head><body>"
    ]
    for pdf, items in previews.items():
        html.append(f"<h2>{pdf}</h2><ul>")
        for lvl, txt, pno, thumb in items:
            b64 = base64.b64encode(open(thumb,"rb").read()).decode()
            html.append(
                f'<li><span class="toggle" onclick="toggle(this)">'
                f'[{lvl}] {txt} (p{pno})</span>'
                f'<div style="display:none;margin-left:20px;">'
                f'<img src="data:image/png;base64,{b64}"/></div></li>'
            )
        html.append("</ul>")
    html.append("</body></html>")
    with open(os.path.join(args.output_dir,"outline.html"),"w",encoding="utf-8") as f:
        f.write("\n".join(html))

    print("✅ Tuned extraction complete: JSON, stats.json, outline.html, thumbnails/")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import re
import json
import time
import argparse
import io
import fitz  # PyMuPDF
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from PIL import Image

# ─── Backwards‑compatible Resampling Filter ───────────────────────────────────
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

def get_body_font_size(doc, max_pages=3):
    """Detect the most common font size (body text)."""
    sizes = []
    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if len(text.split()) >= 3:
                        sizes.append(round(span["size"], 1))
    if not sizes:
        return 12.0
    return Counter(sizes).most_common(1)[0][0]

def is_heading(text, font_size, is_bold, body_size):
    """Determine if text is likely a heading."""
    txt = text.strip()
    if len(txt) < 3 or len(txt) > 100:
        return None
    if txt.lower().startswith(('page ', 'figure ', 'table ')):
        return None
    size_diff = font_size - body_size
    if size_diff >= 4:
        return "H1"
    if size_diff >= 2:
        return "H2"
    if is_bold and size_diff >= 1:
        return "H3" if size_diff < 2 else "H2"
    if re.match(r'^(chapter|section|part)\s+\d+', txt.lower()):
        return "H1"
    if re.match(r'^\d+\.?\s+[A-Z]', txt):
        return "H2"
    if re.match(r'^\d+\.\d+\.?\s+', txt):
        return "H3"
    return None

def extract_headings(doc):
    """Extract headings from PDF via simple heuristics."""
    body_size = get_body_font_size(doc)
    headings = []
    seen = set()
    for pno, page in enumerate(doc, start=1):
        if len(headings) >= 30:
            break
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    font_size = round(span["size"], 1)
                    is_bold = bool(span.get("flags", 0) & 16)
                    level = is_heading(text, font_size, is_bold, body_size)
                    if level:
                        key = (level, re.sub(r'\W+', '', text.lower()), pno)
                        if key not in seen:
                            headings.append({"level": level, "text": text, "page": pno})
                            seen.add(key)
    return headings

def get_title(doc):
    """Extract document title."""
    meta = doc.metadata.get("title", "").strip()
    if meta and len(meta.split()) >= 2:
        return meta
    if doc.page_count == 0:
        return ""
    candidates = []
    for block in doc[0].get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                t = span["text"].strip()
                sz = span["size"]
                if 2 <= len(t.split()) <= 12 and sz >= 14:
                    candidates.append((sz, t, span["bbox"][1]))
    if not candidates:
        return ""
    candidates.sort(key=lambda x: (-x[0], x[2]))
    return candidates[0][1]

def generate_thumbnail(doc, output_path, size=(300, 400), quality=85):
    """Generate a first-page thumbnail at output_path."""
    try:
        if doc.page_count == 0:
            print(f"Warning: no pages to thumbnail: {output_path}")
            return False
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img.thumbnail(size, RESAMPLE)
        # Ensure RGB
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255,255,255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "JPEG", quality=quality, optimize=True)
        return True
    except Exception as e:
        print(f"✗ Thumbnail failed: {e}")
        return False

def process_pdf(pdf_path, output_dir, generate_thumbs=False, thumb_size=(300,400)):
    """Process a single PDF: title, headings, optional thumbnail."""
    fname = os.path.basename(pdf_path)
    base = fname[:-4]
    with fitz.open(pdf_path) as doc:
        title = get_title(doc)
        headings = extract_headings(doc)
        thumb_file = None
        if generate_thumbs:
            thumb_dir = os.path.join(output_dir, "thumbnails")
            thumb_file = os.path.join(thumb_dir, f"{base}.jpg")
            if not generate_thumbnail(doc, thumb_file, thumb_size):
                thumb_file = None
    result = {"file": fname, "headings": len(headings)}
    # write JSON
    out = {"source_file": fname, "title": title, "outline": headings}
    if thumb_file:
        out["thumbnail"] = f"thumbnails/{os.path.basename(thumb_file)}"
    json_path = os.path.join(output_dir, f"{base}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return result

def main():
    p = argparse.ArgumentParser("PDF Outline Extractor")
    p.add_argument("-i","--input-dir", default="input")
    p.add_argument("-o","--output-dir", default="output")
    p.add_argument("-j","--jobs", type=int, default=1,
                   help="0=CPU count, >0 for that many workers")
    p.add_argument("-t","--thumbnails", action="store_true")
    p.add_argument("--thumb-size", nargs=2, type=int, default=[300,400], metavar=("W","H"))
    args = p.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    if args.thumbnails:
        os.makedirs(os.path.join(args.output_dir, "thumbnails"), exist_ok=True)

    pdfs = [os.path.join(args.input_dir,f)
            for f in os.listdir(args.input_dir)
            if f.lower().endswith(".pdf")]
    if not pdfs:
        print("No PDF files found in input directory.")
        return

    workers = cpu_count() if args.jobs==0 else min(args.jobs, len(pdfs))
    start = time.time()
    results = []

    if workers <= 1:
        for pdf in pdfs:
            r = process_pdf(pdf, args.output_dir, args.thumbnails, tuple(args.thumb_size))
            print(f"✅ {r['file']}: {r['headings']} headings")
            results.append(r)
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(process_pdf, pdf, args.output_dir, args.thumbnails, tuple(args.thumb_size))
                       for pdf in pdfs]
            for fut in futures:
                r = fut.result()
                print(f"✅ {r['file']}: {r['headings']} headings")
                results.append(r)

    # write stats.json
    stats = {
        "num_docs": len(results),
        "total_headings": sum(r["headings"] for r in results),
        "avg_headings_per_doc": round(
            sum(r["headings"] for r in results) / len(results), 2
        ) if results else 0.0
    }
    with open(os.path.join(args.output_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start
    print(f"\n🚀 Done in {elapsed:.2f}s | Processed {stats['num_docs']} PDFs | "
          f"Avg headings/PDF: {stats['avg_headings_per_doc']:.2f}")

if __name__ == "__main__":
    main()

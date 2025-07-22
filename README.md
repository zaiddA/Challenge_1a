# PDF Outline Extractor for Adobe Hackathon Round 1A

Welcome! This tool helps you turn any PDF into a neat, structured outline—perfect for quick navigation and downstream processing in your hackathon project.

## ✨ What It Does

* **Title Discovery**: Grabs the title from PDF metadata or finds the biggest text on page 1.
* **Heading Detection**: Spots H1, H2, and H3 headings using font sizes, numbering (e.g., "1.2"), and simple layout cues.
* **Blazing Fast**: Processes up to 50 pages in under 10 seconds on a CPU-only setup.
* **Dockerized**: Package everything in a small (< 200 MB) Docker container. No internet needed.

## 🚀 Getting Started

1. **Clone this repo**

   ```bash
   git clone git@github.com:your_org/your_repo.git
   cd your_repo
   ```

2. **Make folders**

   ```bash
   mkdir input output
   ```

3. **Drop PDFs** into `input/` (e.g., `sample.pdf`).

4. **Build the Docker image**

   ```bash
   docker build --platform=linux/amd64 -t outline-extractor .
   ```

5. **Run the extractor**

   ```bash
   docker run --rm \
     -v ${PWD}/input:/app/input \
     -v ${PWD}/output:/app/output \
     --network none \
     outline-extractor
   ```

6. **Check `output/`** for `.json` files matching your PDFs.

## 🔍 How It Works (Under the Hood)

1. **Title Detection**

   * Tries PDF metadata first.
   * If missing, picks the largest-font text block on page 1.

2. **Finding the Body Font Size**

   * Scans all pages to find the most common font size (the body text size).

3. **Heading Levels**

   * **H1**: Any span ≥ body + 3 pt.
   * **H2**: Any span ≥ body + 1.5 pt.
   * **H3**: Derived from numbering patterns (e.g., “2.1.3”) or bold/indent cues.

4. **Output JSON**

   ```json
   {
     "title": "<your title>",
     "outline": [
       { "level": "H1", "text": "Introduction", "page": 1 },
       { "level": "H2", "text": "Background", "page": 2 },
       { "level": "H3", "text": "History", "page": 3 }
     ]
   }
   ```

## 🛠️ Tips & Tricks

* **Customize thresholds** in `outline_extractor.py` if your PDFs use unusual font sizing.
* **Test different PDFs**: multi-column layouts, no metadata, etc.
* **Performance**: If you hit > 10 s on large docs, add early-exit skips for pages without big fonts.

---

Happy hacking! 🚀 Feel free to tweak the code to match your PDF quirks and reach out if you need help.

# PDF Outline Extractor

This tool converts PDFs into structured outlines (JSON), extracting titles and headings for easy navigation and downstream processing.

---

## Features

- **Title Extraction**: Uses PDF metadata or the largest text on page 1.
- **Heading Detection**: Identifies H1, H2, H3 using font size, numbering, and layout cues.
- **Fast**: Processes up to 50 pages in under 10 seconds (CPU-only).
- **Dockerized**: Fully containerized, no internet required.

---

## Quick Start

### 1. Clone the Repository

```bash
git clone <your_repo_url>
cd <your_repo_directory>
```

### 2. Prepare Input/Output Folders

```bash
mkdir input output
```

Place your PDF files in the `input/` directory.

---

## Option 1: Run with Docker

### 3. Build the Docker Image

```bash
docker build --platform=linux/amd64 -t outline-extractor .
```

### 4. Run the Extractor

```bash
docker run --rm \
  -v "${PWD}/input:/app/input" \
  -v "${PWD}/output:/app/output" \
  --network none \
  outline-extractor
```

- Output JSON files will appear in `output/` with the same base name as your PDFs.

---

## Option 2: Run Locally (No Docker)

### 3. Install Python 3.10+ and Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Extractor

```bash
python outline_extractor.py -i input -o output
```

#### Optional Flags

- `-j 0` — Use all CPU cores for parallel processing.
- `-t` — Generate thumbnails for each PDF (saved in `output/thumbnails/`).
- `--thumb-size W H` — Set thumbnail size (default: 300 400).

**Example:**

```bash
python outline_extractor.py -i input -o output -j 0 -t --thumb-size 400 600
```

---

## Output

- For each PDF, a `.json` file is created in `output/`:
  ```json
  {
    "source_file": "sample.pdf",
    "title": "Document Title",
    "outline": [
      { "level": "H1", "text": "Introduction", "page": 1 },
      { "level": "H2", "text": "Background", "page": 2 },
      { "level": "H3", "text": "History", "page": 3 }
    ],
    "thumbnail": "thumbnails/sample.jpg" // if -t used
  }
  ```
- A summary `stats.json` is also generated.

---

## Troubleshooting

- Ensure your PDFs are in the `input/` folder.
- If you encounter missing dependencies, re-run `pip install -r requirements.txt`.
- For large PDFs or slow performance, try running with `-j 0` for parallel processing.

---

## Customization

- Adjust heading detection thresholds in `outline_extractor.py` if your PDFs use unusual font sizes or layouts.

---

## License

MIT

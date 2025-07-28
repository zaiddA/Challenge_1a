# PDF Outline Extractor - Offline Usage Guide

# ADOBE-1A

## 📥 Cloning the Repository

Before running any steps, clone this repository to your local machine:

```powershell
git clone https://github.com/zaiddA/Challenge_1a.git
cd Challenge_1a
```

---

This tool extracts structured outlines from PDF files using a fully offline, Dockerized workflow. You can use either the main input/output folders or dedicated test folders for your experiments.

---

## 🧪 Running with Test Input/Output Folders

You can use the `testinput` and `testoutput` folders to test the extractor without affecting your main data. Place your sample PDF files in `testinput/` and the results will appear in `testoutput/`.

**Steps:**

1. Open PowerShell and navigate to the `Challenge_1a` directory:

   ```powershell
   cd path\to\Challenge_1a
   ```

2. Run these commands one by one:
   ```powershell
   docker load -i .\python_3.10-slim.tar.gz
   docker build -t challenge1a .
   docker run --rm -v "${PWD}\testinput:/app/input" -v "${PWD}\testoutput:/app/output" challenge1a
   ```

- This will load the Python Docker image from the provided tarball, build your project image, and run it, all completely offline.
- All PDFs in `testinput/` will be processed, and the output JSON files will be saved in `testoutput/`.
- **Note:** The script will automatically create the `testoutput` directory (and the `thumbnails` subfolder, if needed) if they do not exist.
- Make sure Docker is installed and running on your system.

---

## 📂 Running with Main Input/Output Folders

For actual use, place your PDF files in the `input/` folder. The extracted outlines will be saved in the `output/` folder.

**Steps:**

1. Open PowerShell and navigate to the `Challenge_1a` directory:

   ```powershell
   cd path\to\Challenge_1a
   ```

2. Run these commands one by one:
   ```powershell
   docker load -i .\python_3.10-slim.tar.gz
   docker build -t challenge1a .
   docker run --rm -v "${PWD}\input:/app/input" -v "${PWD}\output:/app/output" challenge1a
   ```

- All PDFs in `input/` will be processed, and the output JSON files will be saved in `output/`.
- **Note:** The script will automatically create the `output` directory (and the `thumbnails` subfolder, if needed) if they do not exist.
- This workflow is also fully offline and uses the same Docker image.

---

## ℹ️ Notes

- You can create the `testinput`, `testoutput`, `input`, and `output` folders if they do not already exist.
- The Docker image is loaded from the provided `python_3.10-slim.tar.gz` file, so no internet connection is required.
- If you want to switch between test and main folders, just change the `-v` (volume) arguments in the `docker run` command as shown above.

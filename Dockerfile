# Use a slim, official Python image on amd64
FROM --platform=linux/amd64 python:3.10-slim

# Install system dependencies:
#  - tesseract-ocr + language packs (eng, jpn, spa)
#  - poppler-utils for pdf2image (if you choose to use it later)
#  - libgl1 for Pillow image handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-spa \
    poppler-utils \
    libgl1 && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the extractor script into the container
COPY outline_extractor.py .

# Default command: run the extractor
ENTRYPOINT ["python", "outline_extractor.py"]

# Academic Assessment Integrity Detection System

## Overview

The Academic Assessment Integrity Detection System is an AI-powered plagiarism detection platform designed to assist educators and institutions in identifying copied or unoriginal content in academic submissions.

The system supports text, image, and PDF inputs, performs OCR-based text extraction, and checks for plagiarism using web search (Google Custom Search and Google Scholar) along with AI-assisted processing.

---

## Features

* PDF Processing

  * Extracts text from both digital and scanned PDFs
  * OCR support using Tesseract and image-based extraction

* Image Text Extraction

  * Extracts text from images using OCR and AI models

* Plagiarism Detection

  * Chunk-based plagiarism checking
  * Google Search API integration
  * Google Scholar reference linking

* Chunk-Level Analysis

  * Splits text into segments
  * Detects plagiarism per chunk with source references

* Report Generation

  * Highlights plagiarized sections
  * Generates downloadable reports

* AI Integration

  * Text extraction using OpenAI vision models
  * Optional AI-based summarization and analysis

---

## System Architecture

1. Input (PDF / Image / Text)
2. Text Extraction

   * PyMuPDF / PyPDF2
   * Tesseract OCR
   * OpenAI Vision
3. Text Chunking (300 words)
4. Plagiarism Detection

   * Google Custom Search API
   * Google Scholar
5. Output

   * JSON results
   * Annotated PDF / report

---

## Tech Stack

* Backend: FastAPI
* OCR: Tesseract OCR, PyMuPDF
* AI Integration: OpenAI API
* PDF Processing: PyPDF2, PyMuPDF, ReportLab
* Image Processing: PIL (Pillow)
* Search API: Google Custom Search API

---

## Project Structure

```
├── app.py                     # Main plagiarism API
├── api.py                     # Core plagiarism + OCR endpoints
├── api2.py                    # Advanced processing & AI features
├── pdftest.py                 # PDF OCR extraction module
├── requirements.txt           # Dependencies
└── README.md                  # Project documentation
```

---

## Installation

### 1. Clone the repository

```
git clone https://github.com/your-username/academic-integrity-system.git
cd academic-integrity-system
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Install Tesseract OCR

Download from: https://github.com/tesseract-ocr/tesseract

Update the path in your code if required:

```python
pytesseract.pytesseract.tesseract_cmd = "your/path/to/tesseract"
```

---

## Environment Variables

Do not hardcode API keys in production. Set the following:

```
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
CSE_ID=your_search_engine_id
```

---

## Running the Application

```
uvicorn app:app --reload
```

API will be available at:

```
http://127.0.0.1:8000
```

Swagger documentation:

```
http://127.0.0.1:8000/docs
```

---

## API Endpoints

PDF Processing

* POST /process-pdf
  Upload a PDF and extract text using OCR

Plagiarism Check

* POST /check-plagiarism
  Input: text
  Output: chunk-wise plagiarism results

Image Upload

* POST /upload/image
  Extract text and perform plagiarism detection

PDF Upload with Marking

* POST /upload/pdf
  Returns annotated PDF with highlighted plagiarism

Text Submission

* POST /submit/text
  Direct text plagiarism analysis

---

## Example Output

```
{
  "chunk": "sample text...",
  "page": 1,
  "is_plagiarized": true,
  "google_result": [
    ["https://example.com", "Example Source"]
  ],
  "scholar_url": "https://scholar.google.com/..."
}
```

---

## Limitations

* Depends on Google Search API quota
* OCR accuracy varies with scan quality
* Chunk matching may miss paraphrased plagiarism
* API keys must be secured in production

---

## Future Improvements

* Semantic plagiarism detection using deep learning
* Paraphrase detection using embeddings
* Web-based user interface for educators
* Integration with learning management systems
* Improved PDF highlighting accuracy

---

## Author

Vignesh

---

## License

This project is intended for academic and educational purposes.

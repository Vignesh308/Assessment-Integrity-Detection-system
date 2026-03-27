from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import pymupdf  # This is the correct import for PyMuPDF
from PIL import Image
from io import BytesIO
import pytesseract
import requests
import urllib.parse
import os
import openai

app = FastAPI(title="PDF Text Extractor with OCR")

# Configuration (REMOVE THESE IN PRODUCTION - USE ENVIRONMENT VARIABLES)
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update this path
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
# OpenAI API Key (use environment variables in production)
openai_api_key = "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"
client = openai.OpenAI(api_key=openai_api_key)

# Google Custom Search API Credentials
google_api_key = "AIzaSyAZEw8HwnDzdaZZ9oZB9IdSr6nDPRkR9kc"
cse_id = "10bafa12f01994eb2"

# --- Utility Functions ---
def pdf_to_images(pdf_bytes: bytes) -> list:
    """Convert PDF pages to images using PyMuPDF"""
    images = []
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        return images
    except Exception as e:
        raise RuntimeError(f"PDF to image conversion failed: {str(e)}")

def ocr_image(img: Image.Image) -> str:
    """Perform OCR on a single image"""
    try:
        img = img.convert('L')  # Convert to grayscale
        return pytesseract.image_to_string(img, lang='eng')
    except Exception as e:
        raise RuntimeError(f"OCR failed: {str(e)}")

def extract_text_from_scanned_pdf(pdf_file: BytesIO) -> list:
    """Main OCR extraction function"""
    try:
        images = pdf_to_images(pdf_file.getvalue())
        return [(ocr_image(img), i+1) for i, img in enumerate(images)]
    except Exception as e:
        raise RuntimeError(f"Text extraction failed: {str(e)}")
def chunk_text(text_with_pages, chunk_size=300):
    full_text = " ".join([text for text, _ in text_with_pages])
    words = full_text.split()
    chunks = []
    current_page = 1
    page_texts = {page: text for text, page in text_with_pages}
    
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        for page, page_text in page_texts.items():
            if chunk in page_text:
                current_page = page
                break
        chunks.append((chunk, current_page))
    return chunks

def check_plagiarism_google(chunk):
    snippet = chunk[:50].strip() + "..." if len(chunk) > 50 else chunk
    encoded_snippet = urllib.parse.quote(f'"{snippet}"')
    url = f"https://www.googleapis.com/customsearch/v1?key={google_api_key}&cx={cse_id}&q={encoded_snippet}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        results = response.json()
        items = results.get("items", [])
        if items:
            matches = [(item["link"], item["title"][:50] + "...") for item in items[:3]]
            return True, matches
        return False, "No significant matches found on Google Search."
    except requests.exceptions.RequestException as e:
        return False, f"Error with Google Custom Search API: {e}"

def check_plagiarism_scholar(chunk):
    snippet = chunk[:50].strip() + "..." if len(chunk) > 50 else chunk
    encoded_snippet = urllib.parse.quote(f'"{snippet}"')
    return f"https://scholar.google.com/scholar?q={encoded_snippet}"

# --- API Endpoint ---

@app.post("/check-plagiarism")
async def check_plagiarism(text: str):
    """Check plagiarism for a given text."""
    chunks = chunk_text([(text, 1)])
    results = []
    for i, (chunk, page_num) in enumerate(chunks, 1):
        is_plagiarized, google_result = check_plagiarism_google(chunk)
        scholar_url = check_plagiarism_scholar(chunk)
        results.append({
            "chunk": chunk,
            "page": page_num,
            "is_plagiarized": is_plagiarized,
            "google_result": google_result,
            "scholar_url": scholar_url
        })
    return {"chunks": results}

@app.post("/process-pdf")
async def process_pdf(file: UploadFile = File(...)):
    if not file.content_type == "application/pdf":
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid file type. Only PDFs are accepted."}
        )
    
    try:
        pdf_bytes = BytesIO(await file.read())
        extracted_pages = extract_text_from_scanned_pdf(pdf_bytes)
        
        return {
            "status": "success",
            "page_count": len(extracted_pages),
            "extracted_text": [{
                "page": page_num,
                "text": text
            } for text, page_num in extracted_pages]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Processing failed: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

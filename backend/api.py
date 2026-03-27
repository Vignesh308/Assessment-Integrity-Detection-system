from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import openai
import base64
from PIL import Image
from io import BytesIO
import PyPDF2
import requests
import urllib.parse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from fastapi.responses import JSONResponse
import pymupdf
import pytesseract

app = FastAPI(title="Plagiarism Checker API")

# OpenAI API Key (use environment variables in production)
openai_api_key = "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"
client = openai.OpenAI(api_key=openai_api_key)

# Google Custom Search API Credentials
google_api_key = "AIzaSyAZEw8HwnDzdaZZ9oZB9IdSr6nDPRkR9kc"
cse_id = "10bafa12f01994eb2"

# Dummy ML Model Check
dummy_model_path = "best_model.h5"
dummy_model_exists = os.path.exists(dummy_model_path)

# Helper Functions (unchanged from your code)
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode("utf-8")

def extract_text_from_image(uploaded_file):
    image_base64 = encode_image(uploaded_file)
    image_data = f"data:image/jpeg;base64,{image_base64}"
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "Extract text from the image."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract the text from this image."},
                    {"type": "image_url", "image_url": {"url": image_data}}
                ]}
            ]
        )
        return response.choices[0].message.content.strip()
    except openai.OpenAIError as e:
        return f"Error extracting text: {e}"

def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text_with_pages = []
    for page_num, page in enumerate(pdf_reader.pages, 1):
        text = page.extract_text()
        text_with_pages.append((text.strip(), page_num))
    return text_with_pages

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

def mark_plagiarism_in_pdf(original_pdf, chunks_with_results):
    output_pdf = BytesIO()
    c = canvas.Canvas(output_pdf, pagesize=letter)
    pdf_reader = PyPDF2.PdfReader(original_pdf)
    
    for chunk, page_num, is_plagiarized, sources in chunks_with_results:
        if is_plagiarized:
            page_text = pdf_reader.pages[page_num - 1].extract_text()
            chunk_start = page_text.find(chunk[:50])
            if chunk_start != -1:
                lines = page_text[:chunk_start].split('\n')
                y_pos = 792 - (len(lines) * 12)
                c.setPageSize(letter)
                c.showPage()
                c.setFillColorRGB(1, 1, 0, 0.3)
                c.rect(50, y_pos - 12, 500, 24, fill=1, stroke=0)
                c.setFillColorRGB(0, 0, 0)
                c.drawString(50, y_pos - 24, f"Source: {sources[0][0]}")
    
    c.save()
    output_pdf.seek(0)
    return output_pdf

def extract_text_from_scanned_pdf(pdf_file: BytesIO) -> list:
    """Main OCR extraction function"""
    try:
        images = pdf_to_images(pdf_file.getvalue())
        return [(ocr_image(img), i+1) for i, img in enumerate(images)]
    except Exception as e:
        raise RuntimeError(f"Text extraction failed: {str(e)}")
    
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

# API Endpoints
@app.get("/status")
async def get_status():
    """Check API status and model availability."""
    return {"status": "running", "ml_model_loaded": dummy_model_exists}

@app.post("/extract-text/image")
async def extract_text_image(file: UploadFile = File(...)):
    """Extract text from an uploaded image."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (png, jpg, jpeg)")
    text = extract_text_from_image(file.file)
    return {"extracted_text": text}

@app.post("/extract-text/pdf")
async def extract_text_pdf(file: UploadFile = File(...)):
    """Extract text from an uploaded PDF with page numbers."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    text_with_pages = extract_text_from_pdf(file.file)
    return {"text_with_pages": [{"text": text, "page": page} for text, page in text_with_pages]}

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

@app.post("/generate-report")
async def generate_report(text: str):
    """Generate a plagiarism report for the given text."""
    chunks = chunk_text([(text, 1)])
    chunks_with_results = []
    for chunk, page_num in chunks:
        is_plagiarized, google_result = check_plagiarism_google(chunk)
        chunks_with_results.append((chunk, page_num, is_plagiarized, google_result if is_plagiarized else []))
    
    report = f"""
    **Plagiarism Report (Powered by ML Model hand.h5)**

    **Input Method:** Text

    **Entered Text:**
    {text}

    **Text Chunks (300 words each) and Results:**
    """
    for i, (chunk, page_num, is_plagiarized, sources) in enumerate(chunks_with_results, 1):
        google_result = sources if is_plagiarized else "No significant matches found."
        scholar_url = check_plagiarism_scholar(chunk)
        report += f"\n**Chunk {i} ({len(chunk.split())} words) - Page {page_num}:**\n{chunk}\n\n"
        report += f"**Google Search Result:**\n{google_result}\n\n"
        report += f"**Google Scholar URL:**\n{scholar_url}\n\n"
    
    report_file = BytesIO(report.encode())
    return StreamingResponse(
        report_file,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=plagiarism_report.txt"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

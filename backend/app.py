from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
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
import fitz  # PyMuPDF for better PDF image extraction

# FastAPI app
app = FastAPI(title="Advanced Plagiarism Checker API")

# OpenAI API Key (should be in environment variables in production)
openai_api_key = "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"
client = openai.OpenAI(api_key=openai_api_key)

# Google Custom Search API Credentials
google_api_key = "AIzaSyAZEw8HwnDzdaZZ9oZB9IdSr6nDPRkR9kc"
cse_id = "10bafa12f01994eb2"

# Dummy ML Model check
dummy_model_path = "best_model.h5"
dummy_model_exists = os.path.exists(dummy_model_path)

# Utility Functions (unchanged from original)
def encode_image(uploaded_file: BytesIO):
    return base64.b64encode(uploaded_file.getvalue()).decode("utf-8")

def pdf_page_to_image(pdf_bytes: BytesIO, page_num: int, dpi=300):
    doc = fitz.open(stream=pdf_bytes.getvalue(), filetype="pdf")
    page = doc.load_page(page_num)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    return img_bytes

def is_image_page(page):
    if '/XObject' in page['/Resources']:
        xObject = page['/Resources']['/XObject'].get_object()
        for obj in xObject:
            if xObject[obj]['/Subtype'] == '/Image':
                return True
    return False

def extract_text_from_image(image_bytes: BytesIO):
    image_base64 = encode_image(image_bytes)
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

def extract_text_from_pdf(pdf_file: BytesIO):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text_with_pages = []
    
    for page_num, page in enumerate(pdf_reader.pages, 1):
        try:
            text = page.extract_text()
            if not text.strip() or is_image_page(page):
                img_bytes = pdf_page_to_image(pdf_file, page_num-1)
                text = extract_text_from_image(img_bytes)
            text_with_pages.append((text.strip(), page_num))
        except Exception as e:
            text_with_pages.append((f"Error processing page {page_num}: {str(e)}", page_num))
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

def check_plagiarism_google(chunk: str):
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

def check_plagiarism_scholar(chunk: str):
    snippet = chunk[:50].strip() + "..." if len(chunk) > 50 else chunk
    encoded_snippet = urllib.parse.quote(f'"{snippet}"')
    return f"https://scholar.google.com/scholar?q={encoded_snippet}"

def mark_plagiarism_in_pdf(original_pdf: BytesIO, chunks_with_results):
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

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Welcome to the Advanced Plagiarism Checker API"}

@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    if file.content_type not in ["image/png", "image/jpeg", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    image_bytes = BytesIO(await file.read())
    extracted_text = extract_text_from_image(image_bytes)
    chunks = chunk_text([(extracted_text, 1)])
    
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
    
    return {"extracted_text": extracted_text, "chunks": results}

@app.post("/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    pdf_bytes = BytesIO(await file.read())
    text_with_pages = extract_text_from_pdf(pdf_bytes)
    extracted_text = " ".join([text for text, _ in text_with_pages])
    chunks = chunk_text(text_with_pages)
    
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
    
    marked_pdf = mark_plagiarism_in_pdf(pdf_bytes, [(r["chunk"], r["page"], r["is_plagiarized"], r["google_result"]) for r in results])
    
    return StreamingResponse(
        marked_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=marked_plagiarism.pdf"}
    )

@app.post("/submit/text")
async def submit_text(text: str):
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
    
    return {"submitted_text": text, "chunks": results}

# Run the app with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0",port=8000)

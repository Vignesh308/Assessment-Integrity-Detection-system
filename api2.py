from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import PyPDF2
import pytesseract
import pdf2image
import numpy as np
from PIL import Image
import io
import os
import tempfile
from typing import Optional

app = FastAPI(title="Text Extraction API",
             description="Extract text from PDFs and images with OCR support",
             version="1.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration (use environment variables in production)
OPENAI_API_KEY = "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"  # Replace with your key
openai.api_key = OPENAI_API_KEY

class ExtractionRequest(BaseModel):
    file_type: str  # "pdf" or "image"
    language: str = "eng"
    ocr_config: str = "--psm 6"

class AIProcessingRequest(BaseModel):
    text: str
    task: str  # "summarize", "analyze", "answer"
    question: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1000

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...), request: ExtractionRequest = None):
    """Endpoint for text extraction from PDFs or images"""
    try:
        if request is None:
            request = ExtractionRequest(file_type=file.content_type.split('/')[-1])

        if request.file_type == "pdf" or file.content_type == "application/pdf":
            extracted_text = extract_text_from_pdf(await file.read())
        else:  # Image
            extracted_text = extract_text_from_image(await file.read(), request.language, request.ocr_config)

        if not extracted_text:
            raise HTTPException(status_code=400, detail="No text could be extracted")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as tmp:
            tmp.write(extracted_text)
            tmp_path = tmp.name

        return FileResponse(
            tmp_path,
            media_type="text/plain",
            filename="extracted_text.txt",
            headers={"X-Extracted-Text-Length": str(len(extracted_text))}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-with-ai")
async def process_with_ai(request: AIProcessingRequest):
    """Endpoint for AI text processing"""
    try:
        if request.task == "summarize":
            prompt = f"Summarize this content:\n\n{request.text[:10000]}"
        elif request.task == "analyze":
            prompt = f"Analyze key points:\n\n{request.text[:10000]}"
        elif request.task == "answer":
            if not request.question:
                raise HTTPException(status_code=400, detail="Question is required for answer task")
            prompt = f"Content:\n{request.text[:10000]}\n\nQuestion: {request.question}\nAnswer:"
        else:
            raise HTTPException(status_code=400, detail="Invalid task specified")

        response = openai.ChatCompletion.create(
            model=request.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        return JSONResponse({
            "result": response.choices[0].message.content,
            "usage": response.usage.to_dict()
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF (text-based or scanned)"""
    try:
        # First try regular text extraction
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
            if text.strip():
                return text
        except:
            pass
        
        # If no text, try OCR
        images = pdf2image.convert_from_bytes(
            file_bytes,
            dpi=300,
            thread_count=4
        )
        return perform_ocr(images)
            
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {str(e)}")

def extract_text_from_image(file_bytes: bytes, language: str = "eng", config: str = "--psm 6") -> str:
    """Extract text from image using OCR"""
    try:
        image = Image.open(io.BytesIO(file_bytes))
        return perform_ocr([image], language, config)
    except Exception as e:
        raise RuntimeError(f"Image extraction failed: {str(e)}")

def perform_ocr(images: list, language: str = "eng", config: str = "--psm 6") -> str:
    """Run OCR on PIL images with preprocessing"""
    extracted_text = ""
    
    for img in images:
        # Preprocess image
        img = img.convert('L')  # Grayscale
        img = np.array(img)
        img = (img > 128).astype(np.uint8) * 255  # Thresholding
        img = Image.fromarray(img)
        
        # Run Tesseract OCR
        text = pytesseract.image_to_string(
            img,
            lang=language,
            config=config
        )
        extracted_text += text + "\n\n"
    
    return extracted_text

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
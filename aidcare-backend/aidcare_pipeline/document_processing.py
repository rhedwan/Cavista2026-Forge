from sqlalchemy.orm import Session
from . import crud
from PIL import Image
import pytesseract # For OCR
from pdf2image import convert_from_path 
import os
import shutil
from datetime import datetime

# Ensure TESSERACT_CMD is set in your .env or system environment if tesseract is not in PATH
# Or, if Tesseract is in PATH, this might not be needed.
# try:
#     pytesseract.pytesseract.tesseract_cmd = os.environ.get('TESSERACT_CMD', 'tesseract')
# except Exception as e:
#     print(f"Warning: Could not set tesseract_cmd, ensure tesseract is in PATH. Error: {e}")

TEMP_PDF_PAGE_DIR = "temp_pdf_pages_for_ocr"

def perform_ocr_on_image(image_path: str) -> str:
    try:
        print(f"Performing OCR on image: {image_path}")
        text = pytesseract.image_to_string(Image.open(image_path))
        print(f"OCR successful for image {image_path}.")
        return text
    except Exception as e:
        print(f"Error during OCR for image {image_path}: {e}")
        return f"OCR Error: {e}"

def perform_ocr_on_pdf(pdf_path: str, temp_dir_for_images="temp_pdf_pages") -> str:
    try:
        print(f"Performing OCR on PDF: {pdf_path}")
        os.makedirs(temp_dir_for_images, exist_ok=True)
        images = convert_from_path(pdf_path)
        full_text = []
        print(f"Converted PDF to {len(images)} images.")
        for i, image in enumerate(images):
            temp_img_filename = f"page_{i+1}.png"
            temp_img_path = os.path.join(temp_dir_for_images, temp_img_filename)
            image.save(temp_img_path, "PNG")
            page_text = pytesseract.image_to_string(Image.open(temp_img_path))
            full_text.append(page_text)
            os.remove(temp_img_path) # Clean up temp image
        # shutil.rmtree(temp_dir_for_images) # Clean up temp dir
        print(f"OCR successful for PDF {pdf_path}.")
        return "\n".join(full_text)
    except Exception as e:
        print(f"Error during OCR for PDF {pdf_path}: {e}")
        # import traceback; traceback.print_exc() # For more detailed error
        return f"PDF OCR Error: {e}"


def process_uploaded_document_task(
    db_provider: callable, # Expects SessionLocal from database.py
    document_uuid: str, 
    file_path_on_server: str, 
    original_filename: str, 
    content_type: str
):
    db: Session = db_provider() # Get a new session for this background task
    extracted_text = ""
    status = "processing"
    error_msg = None
    
    try:
        print(f"BACKGROUND TASK: Starting processing for document UUID: {document_uuid}, File: {original_filename}")
        crud.update_document_processing_status(db, document_uuid, status="processing")

        if content_type in ["image/jpeg", "image/png", "image/tiff", "image/bmp", "image/gif"]:
            extracted_text = perform_ocr_on_image(file_path_on_server)
        elif content_type == "application/pdf":
            # Ensure poppler is installed for pdf2image if not using conda package.
            # On Linux: sudo apt-get install poppler-utils
            # On macOS: brew install poppler
            extracted_text = perform_ocr_on_pdf(file_path_on_server)
        elif content_type == "text/plain":
            with open(file_path_on_server, 'r', encoding='utf-8', errors='ignore') as f:
                extracted_text = f.read()
        else:
            error_msg = f"Unsupported content type for text extraction: {content_type}"
            status = "failed"
            print(f"BACKGROUND_TASK: {error_msg}")

        if not error_msg and not extracted_text.strip() and content_type != "text/plain":
             error_msg = "OCR resulted in empty text."
             # status = "failed" # Or "completed_empty"
             print(f"BACKGROUND_TASK: {error_msg} for {original_filename}")


        if not error_msg: # If no error so far
            status = "completed"
        
        crud.update_document_processing_status(db, document_uuid, status, extracted_text, error_msg)
        print(f"BACKGROUND TASK: Document {document_uuid} processing finished. Status: {status}. Text length: {len(extracted_text)}")

    except Exception as e:
        print(f"BACKGROUND TASK CRITICAL ERROR for doc {document_uuid}: {e}")
        import traceback; traceback.print_exc()
        crud.update_document_processing_status(db, document_uuid, "failed", error_msg=f"Critical processing error: {str(e)}")
    finally:
        db.close() 
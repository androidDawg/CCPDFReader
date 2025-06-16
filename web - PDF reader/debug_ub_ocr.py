import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import os
import sys

# --- This script tests if the OCR solution can read the UnionBank PDF file. ---

# --- Step 1: IMPORTANT - CONFIGURE TESSERACT PATH ---
# Please verify this path is correct for your computer.
# This is the default installation path for the Tesseract 5 installer.
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\ferna\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
except Exception as e:
    print(f"Configuration Error: Could not set Tesseract command path. {e}")
    print("Please make sure Tesseract is installed and the path above is correct.")
    sys.exit(1)

# Set the filename to test.
filepath = "UB March Statement.pdf" 

# Check if the file exists.
if not os.path.exists(filepath):
    print(f"Error: File not found at '{filepath}'")
    print("Please make sure 'UB March Statement.pdf' is in the same folder as this script.")
    sys.exit(1)

print(f"--- Attempting OCR on: {filepath} ---")

try:
    # Open the PDF document
    with fitz.open(filepath) as doc:
        if not doc.page_count:
            print("The document has no pages.")
        
        # Loop through each page of the document
        for page_num, page in enumerate(doc, 1):
            print(f"\n----------- OCR on PAGE {page_num} -----------")
            
            # Step 2: Render the page to a high-resolution image
            # We use PyMuPDF to convert the PDF page into a picture.
            pix = page.get_pixmap(dpi=300)  # Higher DPI improves OCR accuracy
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Step 3: Use Tesseract to perform OCR on the image
            # Pytesseract sends the picture to the Tesseract engine you installed.
            text = pytesseract.image_to_string(img)

            if text and text.strip():
                # If text is found, print it.
                print(text)
            else:
                # If no text is found, print a clear message.
                print("OCR could not detect any text on this page.")

except Exception as e:
    print(f"\nAn error occurred during the OCR process: {e}")

print("\n--- End of file ---")
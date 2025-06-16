import fitz  # PyMuPDF is imported as fitz
import sys
import os

# --- This script tests if PyMuPDF can read the UnionBank PDF file. ---

# Set the filename to test.
filepath = "UB March Statement.pdf" 

# Check if the file exists in the current folder.
if not os.path.exists(filepath):
    print(f"Error: File not found at '{filepath}'")
    print("Please make sure the PDF file is in the same directory as this script.")
    sys.exit(1)

print(f"--- Attempting to read text from: {filepath} using PyMuPDF ---")

try:
    # Open the PDF document
    with fitz.open(filepath) as doc:
        if not doc.page_count:
            print("The document has no pages.")
        
        # Loop through each page of the document
        for page_num, page in enumerate(doc, 1):
            print(f"\n----------- PAGE {page_num} -----------")
            text = page.get_text() # Extract text from the page

            if text and text.strip():
                # If text is found, print it.
                print(text)
            else:
                # If no text is found, print a clear message.
                print("No text found on this page.")

except Exception as e:
    print(f"\nAn error occurred while trying to read the file: {e}")

print("\n--- End of file ---")
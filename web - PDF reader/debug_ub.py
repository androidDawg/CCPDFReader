import pdfplumber
import sys

# --- This script is for debugging the UnionBank PDF file. ---

# Use the filename provided from the command line, or a default.
if len(sys.argv) > 1:
    filepath = sys.argv[1]
else:
    # Please make sure 'UB March Statement.pdf' is in the same folder as this script.
    filepath = "UB March Statement.pdf" 

print(f"--- Reading raw text from: {filepath} ---")
print("--- Each line's raw representation is shown to expose hidden characters ---")

try:
    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\n----------- PAGE {page_num} -----------")
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    # repr() is a special function that makes invisible characters (like tabs or weird spaces) visible.
                    print(repr(line)) 
            else:
                print("No text found on this page.")

except Exception as e:
    print(f"\nAn error occurred while trying to read the file: {e}")

print("\n--- End of file ---")
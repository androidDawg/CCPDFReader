from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os
from datetime import datetime
import fitz  # PyMuPDF for OCR
import pdfplumber  # For text-based PDFs
import re
from PIL import Image
import pytesseract

# --- Configure Tesseract Path ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\ferna\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
app.secret_key = 'the_final_hybrid_solution_key'
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

consolidated_data = pd.DataFrame()

def flexible_date_parser(date_str, year):
    date_str = re.sub(r',', '', date_str).strip()
    formats_to_try = ['%B %d %Y', '%b %d %Y', '%d %b %Y']
    for fmt in formats_to_try:
        try:
            if len(date_str.split()) < 3:
                return datetime.strptime(f"{date_str} {year}", fmt)
            else:
                return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

# --- Keywords are now global for both parsers to use ---
KEYWORDS_TO_CATEGORY = {
    "grab": "Transport", "mcdonald": "Food", "jollibee": "Food", "meralco": "Utilities",
    "globe": "Utilities", "sm": "Groceries", "watsons": "Health", "7-eleven": "Groceries",
    "shopee": "Shopping", "lazada": "Shopping", "netflix": "Entertainment", "venchi": "Dining",
    "rustic": "Dining", "barbers": "Personal Care", "petron": "Fuel", "google": "Subscriptions",
    "manam": "Dining", "philippine airl": "Travel", "hotel": "Travel", "landers": "Groceries",
    "starbucks": "Dining", "waltermart": "Groceries", "cafe": "Dining"
}

def parse_text_based_pdf(filepath, filename):
    print(f"Attempting to parse {filename} as a text-based PDF...")
    full_text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() or ""
    
    if not full_text.strip(): return pd.DataFrame()

    expenses = []
    pattern = re.compile(r"^(?:\w+\s\d{1,2}|\d{1,2}\s\w{3})\s+(\w+\s\d{1,2}|\d{1,2}\s\w{3})\s+(.+?)\s+([\d,.-]+\.\d{2}$)")
    year_match = re.search(r'\b(20\d{2})\b', full_text)
    statement_year = int(year_match.group(1)) if year_match else datetime.now().year

    for line in full_text.split('\n'):
        match = pattern.search(line.strip())
        if match:
            date_to_parse, description, amount_str = match.groups()
            date = flexible_date_parser(date_to_parse, statement_year)
            if date and float(amount_str.replace(",", "")) >= 0:
                desc_lower = description.lower()
                category = "Uncategorized"
                for keyword, cat in KEYWORDS_TO_CATEGORY.items():
                    if keyword in desc_lower: category = cat; break
                expenses.append({"Date": date, "Description": description, "Amount": float(amount_str.replace(",", "")), "Category": category, "Source": filename})
    return pd.DataFrame(expenses)

def parse_image_based_pdf_with_ocr(filepath, filename):
    print(f"Attempting to parse {filename} using OCR...")
    full_text = ""
    with fitz.open(filepath) as doc:
        for page in doc:
            # --- THIS IS THE FIX ---
            # Step 1: Render the page to a pixmap
            pix = page.get_pixmap(dpi=300)
            # Step 2: Convert the pixmap to a standard Image object
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            # Step 3: Pass the correct Image object to pytesseract
            full_text += pytesseract.image_to_string(img)
    
    if not full_text.strip(): return pd.DataFrame()

    expenses = []
    pattern = re.compile(r"^(\w{3}\s\d{1,2},\s\d{4})\s+(.+?)\s+PHP\s*([\d,.-]+\.\d{2})")
    year_match = re.search(r'\b(20\d{2})\b', full_text)
    statement_year = int(year_match.group(1)) if year_match else datetime.now().year

    for line in full_text.split('\n'):
        match = pattern.search(line.strip())
        if match:
            date_to_parse, description, amount_str = match.groups()
            date = flexible_date_parser(date_to_parse, statement_year)
            if date and float(amount_str.replace(",", "")) >= 0:
                desc_lower = description.lower()
                category = "Uncategorized"
                for keyword, cat in KEYWORDS_TO_CATEGORY.items():
                    if keyword in desc_lower: category = cat; break
                expenses.append({"Date": date, "Description": description, "Amount": float(amount_str.replace(",", "")), "Category": category, "Source": filename})
    return pd.DataFrame(expenses)

# --- The Main Dispatcher Function ---
def process_pdf_final(filepath):
    filename = os.path.basename(filepath)
    
    # Identify the bank to decide the strategy
    if "UB" in filename:
        return parse_image_based_pdf_with_ocr(filepath, filename)
    else:
        return parse_text_based_pdf(filepath, filename)

# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def upload_page():
    global consolidated_data
    if request.method == 'POST':
        files = request.files.getlist('files[]')
        if not files or files[0].filename == '':
            flash('No files selected for uploading', 'warning')
            return redirect(request.url)
        for file in files:
            if file and file.filename.endswith('.pdf'):
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filepath)
                new_data = process_pdf_final(filepath)
                if new_data is not None and not new_data.empty:
                    consolidated_data = pd.concat([consolidated_data, new_data], ignore_index=True)
                    flash(f'Successfully processed {file.filename}', 'success')
                else:
                    flash(f'Could not extract any transactions from {file.filename}. The format might be unsupported.', 'danger')
            else:
                flash(f'Invalid file format for {file.filename}. Only PDFs are allowed.', 'warning')
        if not consolidated_data.empty:
            consolidated_data['Date'] = pd.to_datetime(consolidated_data['Date'])
            consolidated_data = consolidated_data.drop_duplicates(subset=['Date', 'Description', 'Amount', 'Source']).sort_values(by='Date', ascending=False)
        return redirect(url_for('results_page'))
    return render_template('index.html')

@app.route('/results')
def results_page():
    global consolidated_data
    if not consolidated_data.empty:
        display_df = consolidated_data.copy()
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        cols = ['Date', 'Description', 'Amount', 'Category', 'Source']
        display_df = display_df[cols]
        table = display_df.to_html(classes='table table-striped table-hover', index=False, justify='left')
    else:
        table = "<p>No transaction data to display. Please upload your PDF statements.</p>"
    return render_template('results.html', table=table)

@app.route('/add_entry', methods=['POST'])
def add_entry():
    global consolidated_data
    try:
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        description = request.form['description']
        amount = float(request.form['amount'])
        category = request.form['category']
        new_entry = pd.DataFrame([[date, description, amount, category, 'Manual Entry']], 
                                 columns=['Date', 'Description', 'Amount', 'Category', 'Source'])
        consolidated_data = pd.concat([consolidated_data, new_entry], ignore_index=True)
        consolidated_data = consolidated_data.sort_values(by='Date', ascending=False)
        flash('Manual entry added successfully!', 'success')
    except (ValueError, KeyError) as e:
        flash(f'Error adding manual entry: {e}', 'danger')
    return redirect(url_for('results_page'))

@app.route('/clear', methods=['POST'])
def clear_data():
    global consolidated_data
    consolidated_data = pd.DataFrame()
    flash('All data has been cleared.', 'info')
    return redirect(url_for('results_page'))

if __name__ == "__main__":
    app.run(debug=True)
from flask import Flask, render_template, request, redirect, url_for, flash, Response
import pandas as pd
import os
from datetime import datetime
import fitz
import pdfplumber
import re
from PIL import Image
import pytesseract
import io
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# --- Configure Tesseract Path ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\ferna\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
app.secret_key = 'the_final_complete_app_key'
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

KEYWORDS_TO_CATEGORY = {
    "grab": "Transport", "mcdonald": "Food", "jollibee": "Food", "meralco": "Utilities",
    "globe": "Utilities", "sm": "Groceries", "watsons": "Health", "7-eleven": "Groceries",
    "shopee": "Shopping", "lazada": "Shopping", "netflix": "Entertainment", "venchi": "Dining",
    "rustic": "Dining", "barbers": "Personal Care", "petron": "Fuel", "google": "Subscriptions",
    "manam": "Dining", "philippine airl": "Travel", "hotel": "Travel", "landers": "Groceries",
    "starbucks": "Dining", "waltermart": "Groceries", "cafe": "Dining", "sony": "Entertainment",
    "playstation": "Entertainment", "steam": "Entertainment", "nike": "Shopping", "uniqlo": "Shopping",
    "decathlon": "Shopping", "handyman": "Shopping", "naati": "Miscellaneous"
}

# In app.py, replace the entire parse_text_based_pdf function with this:

def parse_text_based_pdf(filepath, filename):
    full_text = ""
    # --- This is the corrected try-except block using the correct exception ---
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                full_text += page.extract_text() or ""
    except pdfplumber.utils.exceptions.PdfminerException as e:
        # This is the correct exception that handles password errors from the underlying library.
        if "PDFPasswordIncorrect" in str(e):
            flash(f'Could not process "{filename}" because it is password-protected.', 'danger')
        else:
            flash(f'A PDF parsing error occurred with "{filename}": {e}', 'warning')
        return pd.DataFrame()
    except Exception as e:
        # Catch any other unexpected errors
        flash(f'An unexpected error occurred while processing "{filename}": {e}', 'danger')
        return pd.DataFrame()

    if not full_text.strip(): return pd.DataFrame()

    expenses = []
    # This pattern is tuned for clean, text-based PDF data (BPI, Maya)
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

# In app.py, replace the existing parse_image_based_pdf_with_ocr function

def parse_image_based_pdf_with_ocr(filepath, filename):
    print(f"Attempting to parse {filename} using OCR...")
    full_text = ""
    try:
        with fitz.open(filepath) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                full_text += pytesseract.image_to_string(img)
    except ValueError as e:
        if "encrypted" in str(e):
            flash(f'Could not process "{filename}" because it is encrypted/password-protected.', 'danger')
        else:
            flash(f'An unexpected value error occurred with "{filename}": {e}', 'warning')
        return pd.DataFrame()
    except Exception as e:
        flash(f'An unexpected error occurred during OCR processing of "{filename}": {e}', 'danger')
        return pd.DataFrame()
    
    if not full_text.strip(): return pd.DataFrame()

    expenses = []
    
    # --- FINAL, MOST ROBUST PARSER: A line-by-line state machine ---
    date_pattern = re.compile(r"^(\w{3}\s\d{1,2},\s\d{4})")
    amount_pattern = re.compile(r"PHP\s*(-?[\d,]+\.\d{2})")
    
    year_match = re.search(r'\b(20\d{2})\b', full_text)
    statement_year = int(year_match.group(1)) if year_match else datetime.now().year

    current_transaction = None

    for line in full_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        date_match = date_pattern.search(line)
        amount_match = amount_pattern.search(line)

        # If we find a date, it marks the start of a new transaction
        if date_match:
            # If we were already building a transaction, save it before starting a new one
            if current_transaction and 'Amount' in current_transaction:
                # Clean up description before saving
                current_transaction['Description'] = re.sub(r'\s+', ' ', current_transaction.get('Description', '')).strip()
                if "Interest" not in current_transaction['Description'] and "Charge" not in current_transaction['Description'] and "Fee" not in current_transaction['Description']:
                    expenses.append(current_transaction)

            # Start a new transaction
            date_str = date_match.group(1)
            date = flexible_date_parser(date_str, statement_year)
            current_transaction = {'Date': date, 'Description': '', 'Amount': None, 'Source': filename}
            
            # The rest of the line (if any) is part of the description
            description_part = date_pattern.sub('', line).strip()
            if description_part:
                current_transaction['Description'] += description_part + ' '

        # If we find an amount, it marks the end of the current transaction
        elif amount_match and current_transaction:
            amount_str = amount_match.group(1)
            amount = float(amount_str.replace(",", ""))
            
            # The part of the line before the amount is also part of the description
            description_part = amount_pattern.sub('', line).strip()
            if description_part:
                current_transaction['Description'] += description_part

            # Only assign amount if it's a purchase (not a payment)
            if amount >= 0:
                 current_transaction['Amount'] = amount

        # If it's not a date or amount line, it must be part of the description
        elif current_transaction:
            current_transaction['Description'] += line + ' '

    # Save the very last transaction after the loop finishes
    if current_transaction and 'Amount' in current_transaction and current_transaction['Amount'] is not None:
        current_transaction['Description'] = re.sub(r'\s+', ' ', current_transaction.get('Description', '')).strip()
        if "Interest" not in current_transaction['Description'] and "Charge" not in current_transaction['Description'] and "Fee" not in current_transaction['Description']:
            expenses.append(current_transaction)

    # Final categorization step
    for expense in expenses:
        desc_lower = expense['Description'].lower()
        category = "Uncategorized"
        for keyword, cat in KEYWORDS_TO_CATEGORY.items():
            if keyword in desc_lower:
                category = cat
                break
        expense['Category'] = category

    return pd.DataFrame(expenses)

# --- This is the new, more robust dispatcher function ---
def process_pdf_final(filepath):
    filename = os.path.basename(filepath)
    
    # Method 1: Attempt to parse as a standard text-based PDF (for BPI, Maya, etc.)
    print(f"Attempting text-based parsing for {filename}...")
    expenses = parse_text_based_pdf(filepath, filename)
    if not expenses.empty:
        print(f"Success with text-based parsing for {filename}.")
        return expenses
        
    # Method 2: If text-based fails, fallback to the OCR method (for UnionBank)
    print(f"Text-based parsing for {filename} failed or found no data. Falling back to OCR.")
    expenses_ocr = parse_image_based_pdf_with_ocr(filepath, filename)
    if not expenses_ocr.empty:
        print(f"Success with OCR parsing for {filename}.")
        return expenses_ocr
        
    # If both methods fail
    print(f"Could not extract transactions from {filename} with any method.")
    return pd.DataFrame()

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
    table = "<p>No transaction data to display. Please upload your PDF statements.</p>"
    monthly_summary = ""
    categories = sorted(list(set(KEYWORDS_TO_CATEGORY.values())))
    if not consolidated_data.empty:
        display_df = consolidated_data.copy()
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        cols = ['Date', 'Description', 'Amount', 'Category', 'Source']
        display_df['Amount'] = display_df['Amount'].map('{:,.2f}'.format)
        table = display_df[cols].to_html(classes='table table-striped table-hover', index=False, justify='left')
        summary_df = consolidated_data.copy()
        summary_df['Month'] = summary_df['Date'].dt.strftime('%Y-%m')
        pivot_table = pd.pivot_table(summary_df, values='Amount', index='Month', columns='Category', aggfunc='sum', fill_value=0)
        pivot_table['Total'] = pivot_table.sum(axis=1)
        pivot_table.sort_index(ascending=False, inplace=True)
        for col in pivot_table.columns:
            pivot_table[col] = pivot_table[col].map('{:,.2f}'.format)
        monthly_summary = pivot_table.to_html(classes='table table-hover', justify='left')
    return render_template('results.html', table=table, monthly_summary=monthly_summary, categories=categories)

@app.route('/plot.png')
def plot_png():
    global consolidated_data
    if consolidated_data.empty:
        return Response(status=204)
    fig, ax = plt.subplots(figsize=(10, 7))
    spending_by_category = consolidated_data.groupby('Category')['Amount'].mean().sort_values()
    spending_by_category.plot(kind='barh', ax=ax, color='lightcoral')
    ax.set_title('Average Spending by Category')
    ax.set_xlabel('Average Transaction Amount (PHP)')
    ax.set_ylabel('Category')
    plt.tight_layout()
    output = io.BytesIO()
    plt.savefig(output, format='png')
    plt.close(fig)
    output.seek(0)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/export/<file_format>')
def export_file(file_format):
    global consolidated_data
    if consolidated_data.empty:
        flash('No data to export.', 'warning')
        return redirect(url_for('results_page'))
    if file_format == 'csv':
        return Response(
            consolidated_data.to_csv(index=False),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=expenses.csv"}
        )
    elif file_format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            consolidated_data.to_excel(writer, index=False, sheet_name='Expenses')
        output.seek(0)
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-disposition": "attachment; filename=expenses.xlsx"}
        )
    return redirect(url_for('results_page'))

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
    app.run(host='0.0.0.0', debug=True)
import os
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import pdfplumber
import docx
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === Configuration ===
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# === Initialize App ===
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

# === Google Gemini Setup ===
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-pro")

# === Helpers ===
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    try:
        if ext == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                return ''.join(page.extract_text() or '' for page in pdf.pages)
        elif ext == 'docx':
            doc = docx.Document(file_path)
            return ' '.join(para.text for para in doc.paragraphs)
        elif ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
    except Exception as e:
        print(f"Error extracting text: {e}")
    return None

def generate_mcqs(input_text, num_questions):
    prompt = f"""
You are an AI assistant helping to generate multiple-choice questions (MCQs) based on the following content:

\"\"\" 
{input_text}
\"\"\"

Please generate {num_questions} MCQs in this format:
## MCQ
Question: [Your question here]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Correct Answer: [Correct Option]

Make sure questions are clear, options are relevant, and answers are accurate.
"""
    response = model.generate_content(prompt)
    return response.text.strip()

def save_text_to_file(text, filename):
    path = os.path.join(RESULTS_FOLDER, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return path

def save_pdf_from_text(text, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in text.split("## MCQ"):
        mcq = mcq.strip()
        if mcq:
            pdf.multi_cell(0, 10, mcq)
            pdf.ln(5)

    path = os.path.join(RESULTS_FOLDER, filename)
    pdf.output(path)
    return path

# === Routes ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    if 'file' not in request.files:
        flash('No file uploaded!')
        return redirect(url_for('index'))

    file = request.files['file']

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(upload_path)

        extracted_text = extract_text_from_file(upload_path)
        if not extracted_text:
            flash('Failed to extract text from file.')
            return redirect(url_for('index'))

        try:
            num_questions = int(request.form['num_questions'])
        except ValueError:
            flash('Invalid number of questions.')
            return redirect(url_for('index'))

        mcqs = generate_mcqs(extracted_text, num_questions)

        txt_filename = f"mcqs_{filename.rsplit('.', 1)[0]}.txt"
        pdf_filename = f"mcqs_{filename.rsplit('.', 1)[0]}.pdf"

        save_text_to_file(mcqs, txt_filename)
        save_pdf_from_text(mcqs, pdf_filename)

        return render_template('results.html', mcqs=mcqs, txt_filename=txt_filename, pdf_filename=pdf_filename)

    flash('Invalid file type!')
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(RESULTS_FOLDER, filename)
    return send_file(file_path, as_attachment=True)

# === Create folders if not exists ===
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    app.run(debug=True)

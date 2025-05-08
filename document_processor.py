import PyPDF2
from docx import Document
import re
import os
from openai import OpenAI

class DocumentProcessor:
    def __init__(self):
        self.text_cleaners = [
            self._remove_headers_footers,
            self._remove_extra_whitespace,
            self._remove_page_numbers
        ]
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        self.client = OpenAI(api_key=api_key)
    
    def process_document(self, file_path):
        """Process a document and return cleaned text and metadata."""
        text = self._extract_text(file_path)
        for cleaner in self.text_cleaners:
            text = cleaner(text)
        metadata = {
            "file_type": file_path.split('.')[-1].lower(),
            "file_name": os.path.basename(file_path)
        }
        return text, metadata
    
    def _extract_text(self, file_path):
        """Extract text from PDF or DOCX file."""
        if file_path.lower().endswith('.pdf'):
            return self._extract_pdf_text(file_path)
        elif file_path.lower().endswith('.docx'):
            return self._extract_docx_text(file_path)
        else:
            raise ValueError("Unsupported file format")
    
    def _extract_pdf_text(self, file_path):
        """Extract text from PDF file."""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def _extract_docx_text(self, file_path):
        """Extract text from DOCX file."""
        doc = Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    def _remove_headers_footers(self, text):
        """Remove common header and footer patterns."""
        # Remove page numbers
        text = re.sub(r'\n\d+\n', '\n', text)
        # Remove common header/footer patterns
        text = re.sub(r'Page \d+ of \d+', '', text)
        return text
    
    def _remove_extra_whitespace(self, text):
        """Remove extra whitespace and normalize newlines."""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
    
    def _remove_page_numbers(self, text):
        """Remove standalone page numbers."""
        return re.sub(r'^\d+$', '', text, flags=re.MULTILINE) 
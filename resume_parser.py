from pathlib import Path
from typing import Optional, Dict, Any, List
import docx
from pypdf import PdfReader
from config import RESUME_INPUT_DIR

def find_master_resume() -> Optional[Path]:
    """Finds the first .docx or .pdf resume in the input_resume folder."""
    files = list(RESUME_INPUT_DIR.glob("*.docx")) + list(RESUME_INPUT_DIR.glob("*.pdf"))
    if files:
        # Prefer .docx if available
        docx_files = [f for f in files if f.suffix.lower() == ".docx"]
        return docx_files[0] if docx_files else files[0]
    return None

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract plain text from PDF."""
    reader = PdfReader(str(pdf_path))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)
    return "\n".join(pages_text)

def extract_text_from_docx(docx_path: Path) -> str:
    """Extract text from DOCX preserving paragraphs and bullet points."""
    doc = docx.Document(str(docx_path))
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_data:
                full_text.append(" | ".join(row_data))
    return "\n".join(full_text)

def parse_master_resume(resume_path: Optional[Path] = None) -> Dict[str, Any]:
    """Parses master resume into text representation."""
    if resume_path is None:
        resume_path = find_master_resume()

    if not resume_path or not resume_path.exists():
        raise FileNotFoundError(
            f"No master resume found in '{RESUME_INPUT_DIR}'. "
            "Please place your base resume (.docx or .pdf) in the 'input_resume/' folder."
        )

    ext = resume_path.suffix.lower()
    if ext == ".docx":
        raw_text = extract_text_from_docx(resume_path)
    elif ext == ".pdf":
        raw_text = extract_text_from_pdf(resume_path)
    else:
        raise ValueError(f"Unsupported resume extension: {ext}. Must be .docx or .pdf")

    return {
        "file_path": str(resume_path),
        "file_name": resume_path.name,
        "format": ext,
        "raw_text": raw_text
    }

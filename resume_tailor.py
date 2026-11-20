import os
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from openai import OpenAI

from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_BASE_URL,
    RESUME_OUTPUT_DIR,
    USER_PROFILE
)
from resume_parser import parse_master_resume

def clean_json_text(text: str) -> str:
    """Strip markdown code fence if model returns ```json ... ```"""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()

def build_docx_resume(
    data: Dict[str, Any],
    output_path: Path
) -> Path:
    """Builds a polished ATS-friendly DOCX resume from tailored data."""
    doc = docx.Document()

    # Set 0.75-inch margins
    for s in doc.sections:
        s.top_margin = Inches(0.75)
        s.bottom_margin = Inches(0.75)
        s.left_margin = Inches(0.75)
        s.right_margin = Inches(0.75)

    # 1. Header / Name
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = title_p.add_run(USER_PROFILE.get("full_name", "Jane Doe").upper())
    name_run.bold = True
    name_run.font.size = Pt(20)
    name_run.font.name = "Arial"

    # Contact Info
    contact_p = doc.add_paragraph()
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_line = f"{USER_PROFILE.get('city', '')}, {USER_PROFILE.get('state', '')} (Remote) | {USER_PROFILE.get('phone', '')} | {USER_PROFILE.get('email', '')}"
    c_run = contact_p.add_run(contact_line)
    c_run.font.size = Pt(10)
    c_run.font.name = "Arial"

    def add_section_header(title: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(title.upper())
        r.bold = True
        r.font.size = Pt(11)
        r.font.name = "Arial"
        r.font.color.rgb = RGBColor(0, 51, 102)

    # 2. Professional Summary
    add_section_header("Professional Summary")
    sum_p = doc.add_paragraph()
    sum_p.paragraph_format.space_after = Pt(6)
    s_run = sum_p.add_run(data.get("summary", ""))
    s_run.font.size = Pt(10)
    s_run.font.name = "Arial"

    # 3. Core Competencies
    add_section_header("Core Competencies & Key Skills")
    skills_p = doc.add_paragraph()
    skills_p.paragraph_format.space_after = Pt(6)
    skills_text = " | ".join(data.get("skills", []))
    sk_run = skills_p.add_run(skills_text)
    sk_run.font.size = Pt(10)
    sk_run.font.name = "Arial"

    # 4. Professional Experience
    add_section_header("Professional Experience")
    for exp in data.get("experience", []):
        j_p = doc.add_paragraph()
        j_p.paragraph_format.space_after = Pt(1)
        j_title = j_p.add_run(f"{exp.get('title', '')} | {exp.get('company', '')}")
        j_title.bold = True
        j_title.font.size = Pt(10.5)
        j_title.font.name = "Arial"

        d_p = doc.add_paragraph()
        d_p.paragraph_format.space_after = Pt(3)
        d_run = d_p.add_run(exp.get("dates", ""))
        d_run.italic = True
        d_run.font.size = Pt(9.5)
        d_run.font.name = "Arial"

        bullets = exp.get("bullets", [])
        for i, bullet in enumerate(bullets):
            b_p = doc.add_paragraph(style="List Bullet")
            b_p.paragraph_format.space_after = Pt(2 if i < len(bullets) - 1 else 6)
            b_run = b_p.add_run(bullet)
            b_run.font.size = Pt(10)
            b_run.font.name = "Arial"

    # 5. Education & Certifications
    if data.get("education"):
        add_section_header("Education & Certifications")
        for edu in data.get("education", []):
            e_p = doc.add_paragraph()
            e_p.paragraph_format.space_after = Pt(2)
            e_run = e_p.add_run(edu)
            e_run.font.size = Pt(10)
            e_run.font.name = "Arial"

    doc.save(str(output_path))
    return output_path

def tailor_resume_for_job(
    job_title: str,
    company: str,
    job_description: str,
    job_key: str
) -> Dict[str, Any]:
    """Uses Google Gemini to tailor the base resume to match the target job description."""
    base_resume = parse_master_resume()

    system_prompt = (
        "You are an expert ATS resume optimization and career coach. "
        "Your task is to take a candidate's base resume and tailor it specifically for a target job posting. "
        "STRICT RULES:\n"
        "1. DO NOT fabricate false employers, dates, credentials, or achievements.\n"
        "2. Align the Professional Summary to reflect the exact mission and needs of this role.\n"
        "3. Incorporate relevant terminology, keywords, tools (e.g. Zendesk, Salesforce, chat etiquette, SLAs) from the job description.\n"
        "4. Emphasize bullet points that directly address requirements mentioned in the job description.\n"
        "5. Output must be strictly valid JSON matching this schema:\n"
        "{\n"
        '  "summary": "Tailored 3-4 sentence professional summary",\n'
        '  "skills": ["Skill 1", "Skill 2", "Skill 3", ...],\n'
        '  "experience": [\n'
        "    {\n"
        '      "title": "Job Title",\n'
        '      "company": "Company Name",\n'
        '      "dates": "Dates",\n'
        '      "bullets": ["Tailored bullet 1", "Tailored bullet 2", ...]\n'
        "    }\n"
        "  ],\n"
        '  "education": ["Degree or certification 1", ...],\n'
        '  "tailor_notes": "Brief explanation of how the resume was adjusted for this specific role",\n'
        '  "match_score": 85\n'
        "}"
    )

    user_prompt = (
        f"TARGET JOB POSTING:\n"
        f"Title: {job_title}\n"
        f"Company: {company}\n"
        f"Description:\n{job_description}\n\n"
        f"CANDIDATE BASE RESUME:\n{base_resume['raw_text']}"
    )

    if not OPENROUTER_API_KEY:
        # Fallback heuristic mode when API key is not yet set
        print("[WARNING] OPENROUTER_API_KEY is not set. Generating standard tailored template.")
        tailored_data = {
            "summary": f"Customer-focused Remote Support Professional eager to bring proven communication, issue resolution, and customer satisfaction skills to {company} as a {job_title}.",
            "skills": [
                "Customer Service Excellence", "Remote Collaboration", "Omnichannel Ticketing",
                "Conflict Resolution & De-escalation", "Active Listening", "Problem Solving",
                "CRM Proficiency", "SLA Adherence"
            ],
            "experience": [
                {
                    "title": "Senior Customer Support Representative",
                    "company": "Apex Cloud Solutions (Remote)",
                    "dates": "March 2022 – Present",
                    "bullets": [
                        f"Resolved 60+ inbound customer inquiries daily aligned with standards required for {job_title}.",
                        "Maintained 97% CSAT score through patient de-escalation and prompt response times.",
                        "Utilized CRM tools and ticketing workflows to streamline cross-departmental escalations."
                    ]
                },
                {
                    "title": "Customer Care Associate",
                    "company": "Horizon Retail Logistics (Remote)",
                    "dates": "January 2019 – February 2022",
                    "bullets": [
                        "Provided front-line support via chat, email, and phone for customer inquiries.",
                        "Achieved Agent of the Quarter for consistent quality scores and high attendance reliability."
                    ]
                }
            ],
            "education": [
                "Associate of Arts in Business Administration | Dallas College",
                "Certified Customer Service Professional (CCSP)"
            ],
            "tailor_notes": f"Fallback template generated for {job_title} at {company}. Add your OPENROUTER_API_KEY to .env for AI-powered tailoring.",
            "match_score": 75
        }
    else:
        try:
            client = OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=OPENROUTER_API_KEY,
                default_headers={
                    "HTTP-Referer": "https://github.com/indeed-automation",
                    "X-Title": "Indeed Job Automation",
                }
            )
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            cleaned = clean_json_text(response.choices[0].message.content or "{}")
            tailored_data = json.loads(cleaned)
        except Exception as e:
            print(f"[ERROR] OpenRouter tailoring API call failed: {e}. Using fallback generator.")
            tailored_data = {
                "summary": f"Dedicated customer service professional applying for {job_title} at {company}.",
                "skills": ["Customer Support", "Troubleshooting", "Communication", "CRM Tools"],
                "experience": [],
                "education": [],
                "tailor_notes": f"API error fallback: {str(e)}",
                "match_score": 70
            }

    # Safe filename
    safe_company = re.sub(r"[^\w\-_\. ]", "_", company or "Company")[:30].strip()
    safe_title = re.sub(r"[^\w\-_\. ]", "_", job_title or "Job")[:30].strip()
    out_filename = f"Resume_{safe_company}_{job_key}.docx"
    out_path = RESUME_OUTPUT_DIR / out_filename

    build_docx_resume(tailored_data, out_path)

    return {
        "file_path": str(out_path),
        "file_name": out_filename,
        "summary": tailored_data.get("summary", ""),
        "tailor_notes": tailored_data.get("tailor_notes", ""),
        "match_score": tailored_data.get("match_score", 0),
        "data": tailored_data
    }

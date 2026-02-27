"""
Resume Service - Resume tailoring and PDF generation
"""
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from src.services.supabase_client import supabase_client


class ResumeService:
    """
    Service for resume management, tailoring, and PDF generation.
    """
    
    def __init__(self):
        self.templates_cache = {}
    
    async def get_templates(self) -> list:
        """Fetch all available resume templates."""
        response = supabase_client.table("resume_templates").select("*").execute()
        return response.data or []
    
    async def get_template_by_type(self, template_type: str = "ats") -> Optional[Dict]:
        """Fetch a template by type/name."""
        if template_type in self.templates_cache:
            return self.templates_cache[template_type]
        
        # Query by name (case-insensitive partial match)
        response = supabase_client.table("resume_templates").select("*").ilike(
            "name", f"%{template_type}%"
        ).limit(1).execute()
        
        if response.data and len(response.data) > 0:
            self.templates_cache[template_type] = response.data[0]
            return response.data[0]
        
        return None
    
    async def get_default_template(self) -> Optional[Dict]:
        """Fetch the default template."""
        response = supabase_client.table("resume_templates").select("*").eq(
            "is_default", True
        ).single().execute()
        return response.data
    
    def fill_template(
        self,
        template_latex: str,
        profile_data: Dict,
        tailored_content: Dict = None
    ) -> str:
        """
        Fill a LaTeX template with profile and tailored content.
        
        Args:
            template_latex: LaTeX template string with placeholders
            profile_data: User profile data
            tailored_content: AI-tailored content (overrides profile_data)
            
        Returns:
            Filled LaTeX string
        """
        # Use tailored content if available, otherwise use profile
        content = tailored_content or profile_data
        personal = content.get("personal_information", content.get("personal_info", {}))
        
        # Escape LaTeX special characters
        def escape_latex(text: str) -> str:
            if not text:
                return ""
            special_chars = {
                '&': r'\&',
                '%': r'\%',
                '$': r'\$',
                '#': r'\#',
                '_': r'\_',
                '{': r'\{',
                '}': r'\}',
                '~': r'\textasciitilde{}',
                '^': r'\textasciicircum{}',
            }
            for char, escaped in special_chars.items():
                text = text.replace(char, escaped)
            return text
        
        # Build replacements - support both <<PLACEHOLDER>> and {{PLACEHOLDER}} formats
        replacements = {
            # <<FORMAT>>
            "<<NAME>>": escape_latex(personal.get("full_name", "")),
            "<<EMAIL>>": escape_latex(personal.get("email", "")),
            "<<PHONE>>": escape_latex(personal.get("phone", "")),
            "<<LOCATION>>": escape_latex(personal.get("location", personal.get("city", ""))),
            "<<LINKEDIN>>": personal.get("linkedin", ""),
            "<<GITHUB>>": personal.get("github", ""),
            "<<PORTFOLIO>>": personal.get("portfolio", personal.get("website", "")),
            # {{FORMAT}} - for Harish Pro template
            "{{FULL_NAME}}": escape_latex(personal.get("full_name", "")),
            "{{EMAIL}}": escape_latex(personal.get("email", "")),
            "{{PHONE}}": escape_latex(personal.get("phone", "")),
            "{{LINKEDIN_URL}}": personal.get("linkedin", ""),
            "{{GITHUB_URL}}": personal.get("github", ""),
            "{{PORTFOLIO_URL}}": personal.get("portfolio", personal.get("website", "")),
        }
        
        # Summary
        summary = content.get("summary", content.get("professional_summary", ""))
        if isinstance(summary, list):
            summary = " ".join(summary)
        replacements["<<SUMMARY>>"] = escape_latex(summary)
        replacements["{{SUMMARY}}"] = escape_latex(summary)
        
        # Skills - both formats
        skills = content.get("skills", {})
        skills_text = self._format_skills(skills)
        replacements["<<SKILLS>>"] = skills_text
        
        # Individual skill categories for {{FORMAT}}
        if isinstance(skills, dict):
            primary = skills.get("primary", skills.get("technical", []))
            secondary = skills.get("secondary", skills.get("soft", []))
            tools = skills.get("tools", skills.get("frameworks", []))
            
            replacements["{{PRIMARY_SKILLS}}"] = ", ".join(primary) if isinstance(primary, list) else str(primary)
            replacements["{{SECONDARY_SKILLS}}"] = ", ".join(secondary) if isinstance(secondary, list) else str(secondary)
            replacements["{{TOOLS}}"] = ", ".join(tools) if isinstance(tools, list) else str(tools)
        
        # Experience
        experience = content.get("experience", [])
        experience_text = self._format_experience(experience)
        replacements["<<EXPERIENCE>>"] = experience_text
        replacements["{{EXPERIENCE_ENTRIES}}"] = experience_text
        
        # Projects
        projects = content.get("projects", [])
        projects_text = self._format_projects(projects)
        replacements["<<PROJECTS>>"] = projects_text
        replacements["{{PROJECT_ENTRIES}}"] = projects_text
        
        # Education
        education = content.get("education", [])
        education_text = self._format_education(education)
        replacements["<<EDUCATION>>"] = education_text
        replacements["{{EDUCATION_ENTRIES}}"] = education_text
        
        # Achievements and Certifications for {{FORMAT}}
        achievements = content.get("achievements", [])
        if isinstance(achievements, list):
            replacements["{{ACHIEVEMENTS}}"] = " \\\\\n".join(achievements)
        else:
            replacements["{{ACHIEVEMENTS}}"] = str(achievements) if achievements else ""
        
        certifications = content.get("certifications", [])
        if isinstance(certifications, list):
            replacements["{{CERTIFICATIONS}}"] = " $|$ ".join(certifications)
        else:
            replacements["{{CERTIFICATIONS}}"] = str(certifications) if certifications else ""
        
        # Apply replacements
        result = template_latex
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value or "")
        
        return result
    
    def _format_skills(self, skills: Dict) -> str:
        """Format skills section for LaTeX."""
        if not skills:
            return ""
        
        lines = []
        
        # Handle different skill formats
        if isinstance(skills, dict):
            for category, skill_list in skills.items():
                if isinstance(skill_list, list):
                    skills_str = ", ".join(skill_list)
                else:
                    skills_str = str(skill_list)
                category_clean = category.replace("_", " ").title()
                lines.append(f"\\textbf{{{category_clean}:}} {skills_str}")
        elif isinstance(skills, list):
            lines.append(", ".join(skills))
        
        return " \\\\\n".join(lines)
    
    def _format_experience(self, experience: list) -> str:
        """Format experience section for LaTeX."""
        if not experience:
            return ""
        
        entries = []
        for exp in experience:
            company = exp.get("company", "")
            role = exp.get("title", exp.get("role", ""))
            dates = exp.get("dates", exp.get("duration", ""))
            location = exp.get("location", "")
            
            entry = f"\\textbf{{{role}}} \\hfill {dates}\\\\\n"
            entry += f"\\textit{{{company}}} \\hfill {location}\n"
            
            # Responsibilities/highlights
            highlights = exp.get("highlights", exp.get("responsibilities", exp.get("description", [])))
            if highlights:
                entry += "\\begin{itemize}[leftmargin=*, noitemsep]\n"
                if isinstance(highlights, str):
                    highlights = [highlights]
                for item in highlights[:5]:  # Limit to 5 items
                    # Escape LaTeX special chars
                    item = item.replace('&', r'\&').replace('%', r'\%').replace('$', r'\$')
                    entry += f"  \\item {item}\n"
                entry += "\\end{itemize}\n"
            
            entries.append(entry)
        
        return "\n\\vspace{6pt}\n".join(entries)
    
    def _format_projects(self, projects: list) -> str:
        """Format projects section for LaTeX."""
        if not projects:
            return ""
        
        entries = []
        for proj in projects:
            name = proj.get("name", proj.get("title", ""))
            technologies = proj.get("technologies", proj.get("tech_stack", []))
            description = proj.get("description", "")
            url = proj.get("url", proj.get("link", ""))
            
            if isinstance(technologies, list):
                tech_str = ", ".join(technologies)
            else:
                tech_str = technologies
            
            entry = f"\\textbf{{{name}}}"
            if tech_str:
                entry += f" | \\textit{{{tech_str}}}"
            if url:
                entry += f" | \\href{{{url}}}{{Link}}"
            entry += "\n"
            
            if description:
                if isinstance(description, list):
                    entry += "\\begin{itemize}[leftmargin=*, noitemsep]\n"
                    for item in description[:3]:
                        item = item.replace('&', r'\&').replace('%', r'\%')
                        entry += f"  \\item {item}\n"
                    entry += "\\end{itemize}\n"
                else:
                    description = description.replace('&', r'\&').replace('%', r'\%')
                    entry += f"{description}\n"
            
            entries.append(entry)
        
        return "\n\\vspace{4pt}\n".join(entries)
    
    def _format_education(self, education: list) -> str:
        """Format education section for LaTeX."""
        if not education:
            return ""
        
        entries = []
        for edu in education:
            institution = edu.get("institution", edu.get("school", ""))
            degree = edu.get("degree", "")
            field = edu.get("field_of_study", edu.get("major", ""))
            dates = edu.get("dates", edu.get("graduation_date", ""))
            gpa = edu.get("gpa", "")
            
            entry = f"\\textbf{{{institution}}} \\hfill {dates}\\\\\n"
            if degree and field:
                entry += f"{degree} in {field}"
            elif degree:
                entry += degree
            
            if gpa:
                entry += f" | GPA: {gpa}"
            
            entries.append(entry)
        
        return "\n\\vspace{4pt}\n".join(entries)
    
    def compile_to_pdf(
        self,
        latex_content: str,
        output_path: str = None
    ) -> Optional[str]:
        """
        Compile LaTeX content to PDF.
        
        Args:
            latex_content: Complete LaTeX document
            output_path: Optional output path for PDF
            
        Returns:
            Path to generated PDF or None if failed
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "resume.tex"
            pdf_path = Path(tmpdir) / "resume.pdf"
            
            # Write LaTeX file
            tex_path.write_text(latex_content, encoding='utf-8')
            
            try:
                # Try pdflatex first
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, str(tex_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if pdf_path.exists():
                    if output_path:
                        import shutil
                        shutil.copy(pdf_path, output_path)
                        return output_path
                    else:
                        # Return PDF content as bytes
                        return pdf_path.read_bytes()
                else:
                    print(f"LaTeX compilation failed: {result.stderr}")
                    return None
                    
            except FileNotFoundError:
                print("pdflatex not found. Install TeX Live or MiKTeX.")
                return None
                return None
            except subprocess.TimeoutExpired:
                print("LaTeX compilation timed out.")
                return None
                
    def compile_to_pdf_fallback(
        self,
        resume_content: Dict,
        output_path: str
    ) -> Optional[str]:
        """
        Generate a simple Markdown-based PDF fallback using FPDF if LaTeX compilation fails.
        """
        try:
            from fpdf import FPDF
            
            # Simple text cleaner
            def clean_text(txt):
                if not txt: return ""
                # Replace unsupported characters for latin-1
                return str(txt).encode('latin-1', 'replace').decode('latin-1')

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            personal = resume_content.get("personal_information", {})
            name = clean_text(personal.get("full_name", "Candidate"))
            
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, txt=name, ln=True, align='C')
            
            pdf.set_font("Arial", size=10)
            contact = clean_text(f"{personal.get('email', '')} | {personal.get('phone', '')}")
            if personal.get('linkedin'):
                contact += f" | {clean_text(personal.get('linkedin'))}"
            pdf.cell(0, 8, txt=contact, ln=True, align='C')
            
            pdf.ln(5)
            
            # Summary
            summary = resume_content.get("summary", "")
            if summary:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, txt="Professional Summary", ln=True)
                pdf.set_font("Arial", size=11)
                pdf.multi_cell(0, 6, txt=clean_text(summary))
                pdf.ln(5)
                
            # Skills
            skills = resume_content.get("skills", {})
            if skills:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, txt="Skills", ln=True)
                pdf.set_font("Arial", size=11)
                if isinstance(skills, dict):
                    skill_str = ""
                    for k, v in skills.items():
                        v_str = ", ".join(v) if isinstance(v, list) else str(v)
                        skill_str += f"{k.title()}: {v_str}\n"
                    pdf.multi_cell(0, 6, txt=clean_text(skill_str))
                elif isinstance(skills, list):
                    pdf.multi_cell(0, 6, txt=clean_text(", ".join(skills)))
                pdf.ln(5)
                
            # Experience
            experience = resume_content.get("experience", [])
            if experience:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, txt="Experience", ln=True)
                for exp in experience:
                    pdf.set_font("Arial", 'B', 11)
                    title_company = clean_text(f"{exp.get('title', '')} at {exp.get('company', '')}")
                    pdf.cell(0, 6, txt=title_company, ln=True)
                    
                    pdf.set_font("Arial", size=11)
                    for h in exp.get('highlights', []):
                        pdf.multi_cell(0, 6, txt=clean_text(f"- {h}"))
                    pdf.ln(3)
            
            pdf.output(output_path)
            return output_path
            
        except ImportError:
            print("fpdf2 not installed. Cannot generate fallback PDF.")
            return None
        except Exception as e:
            print(f"Fallback PDF generation failed: {e}")
            return None
    
    def _extract_all_skills(self, resume_content: Dict) -> list:
        skills = resume_content.get("skills", {})
        extracted = []
        if isinstance(skills, dict):
            for category_skills in skills.values():
                if isinstance(category_skills, list):
                    extracted.extend(category_skills)
        elif isinstance(skills, list):
            extracted.extend(skills)
        return extracted

    def calculate_ats_score(self, resume_content: Dict, job_requirements: Dict) -> int:
        """
        Calculate ATS compatibility score using robust NLP matching (Spacy).
        
        Factors:
        - NLP Keyword/Lemma matching
        - Skills coverage
        - Section completeness
        """
        score = 0
        max_score = 100
        
        # 1. Skills matching (40 points) using NLP
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            def get_lemmas(text_list):
                if not text_list: return set()
                text = " ".join([str(t) for t in text_list]).lower()
                doc = nlp(text)
                return set(token.lemma_ for token in doc if not token.is_stop and token.is_alpha)
            
            user_skills = get_lemmas(self._extract_all_skills(resume_content))
            required_skills = get_lemmas(job_requirements.get("tech_stack", []))
            
        except Exception as e:
            # Fallback to simple matching if Spacy fails or isn't installed
            print(f"Spacy NLP fallback triggered for ATS scoring: {e}")
            user_skills = set(str(s).lower() for s in self._extract_all_skills(resume_content))
            required_skills = set(str(s).lower() for s in job_requirements.get("tech_stack", []))
        
        if required_skills:
            matching = len(user_skills & required_skills)
            skill_score = min(40, int(40 * matching / len(required_skills)))
            score += skill_score
        else:
            score += 30  # Default if no requirements specified
        
        # 2. Section completeness (30 points)
        sections = ["personal_information", "experience", "education", "skills"]
        present_sections = sum(1 for s in sections if resume_content.get(s))
        score += int(30 * present_sections / len(sections))
        
        # 3. Experience relevance (20 points)
        experience = resume_content.get("experience", [])
        if experience:
            score += min(20, len(experience) * 5)
        
        # 4. Contact info completeness (10 points)
        personal = resume_content.get("personal_information", {})
        contact_fields = ["email", "phone", "linkedin"]
        present_contact = sum(1 for f in contact_fields if personal.get(f))
        score += int(10 * present_contact / len(contact_fields))
        
        return min(score, max_score)


# Singleton instance
resume_service = ResumeService()

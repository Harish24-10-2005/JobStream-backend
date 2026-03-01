"""
PDF Service - Generates professional "Insider Dossier" reports.
Uses ReportLab to create high-quality PDFs from agent JSON data.
"""

import os
from typing import Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PDFService:
	"""Generates PDF reports for JobAI agents."""

	def __init__(self, output_dir: str = 'generated_reports'):
		self.output_dir = output_dir
		os.makedirs(output_dir, exist_ok=True)
		self.styles = getSampleStyleSheet()
		self._setup_custom_styles()

	def _setup_custom_styles(self):
		"""Define custom paragraph styles."""
		self.styles.add(
			ParagraphStyle(
				name='DossierTitle',
				parent=self.styles['Heading1'],
				fontSize=24,
				leading=28,
				textColor=colors.HexColor('#1f2937'),
				spaceAfter=20,
			)
		)
		self.styles.add(
			ParagraphStyle(
				name='SectionHeader',
				parent=self.styles['Heading2'],
				fontSize=16,
				leading=20,
				textColor=colors.HexColor('#111827'),
				borderPadding=(0, 0, 5, 0),
				borderWidth=1,
				borderColor=colors.HexColor('#e5e7eb'),
				spaceAfter=10,
			)
		)
		self.styles.add(
			ParagraphStyle(name='RiskHigh', parent=self.styles['Normal'], textColor=colors.red, fontSize=10, leading=12)
		)

	def generate_company_dossier(self, data: Dict, filename: str) -> str:
		"""
		Generate "The Insider Dossier" - A professional company brief.

		Structure:
		1. Executive Summary
		2. Culture Analysis
		3. Red Flags (Highlighted)
		4. Interview Cheat Sheet
		"""
		file_path = os.path.join(self.output_dir, filename)
		doc = SimpleDocTemplate(file_path, pagesize=LETTER, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)

		story = []
		company = data.get('company', 'Target Company')
		info = data.get('company_info', {})
		culture = data.get('culture_analysis', {})
		flags = data.get('red_flags', {})
		insights = data.get('interview_insights', {})

		# --- TITLE PAGE ---
		story.append(Spacer(1, 1 * inch))
		story.append(Paragraph('CONFIDENTIAL INSIDER DOSSIER', self.styles['Normal']))
		story.append(Paragraph(company, self.styles['DossierTitle']))
		story.append(Paragraph(f'Industry: {info.get("industry", "N/A")}', self.styles['Heading3']))
		story.append(Spacer(1, 0.5 * inch))

		# Quick Stats Table
		stats_data = [
			['Headquarters', info.get('headquarters', 'N/A')],
			['Employees', info.get('employee_count', 'N/A')],
			['Founded', info.get('founded', 'N/A')],
			['Risk Level', flags.get('overall_risk_level', 'Unknown').upper()],
		]
		t = Table(stats_data, colWidths=[2 * inch, 4 * inch])
		t.setStyle(
			TableStyle(
				[
					('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
					('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
					('ALIGN', (0, 0), (-1, -1), 'LEFT'),
					('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
					('FONTSIZE', (0, 0), (-1, -1), 10),
					('BOTTOMPADDING', (0, 0), (-1, -1), 8),
					('TOPPADDING', (0, 0), (-1, -1), 8),
					('GRID', (0, 0), (-1, -1), 0.5, colors.white),
				]
			)
		)
		story.append(t)
		story.append(PageBreak())

		# --- CULTURE ---
		story.append(Paragraph('Culture & Vibe Check', self.styles['SectionHeader']))

		culture_text = []
		culture_text.append(f'<b>Type:</b> {culture.get("culture_type", "N/A")}')
		culture_text.append(
			f'<b>Work-Life Balance:</b> {culture.get("work_life_balance", {}).get("rating", "N/A")} - {culture.get("work_life_balance", {}).get("notes", "")}'
		)

		for line in culture_text:
			story.append(Paragraph(line, self.styles['Normal']))
			story.append(Spacer(1, 6))

		story.append(Paragraph('<b>Pros:</b>', self.styles['Normal']))
		for p in culture.get('pros', []):
			story.append(Paragraph(f'• {p}', self.styles['Normal']))

		story.append(Spacer(1, 10))
		story.append(Paragraph('<b>Cons:</b>', self.styles['Normal']))
		for c in culture.get('cons', []):
			story.append(Paragraph(f'• {c}', self.styles['Normal']))

		story.append(Spacer(1, 20))

		# --- RED FLAGS ---
		story.append(Paragraph('Risk Assessment', self.styles['SectionHeader']))
		story.append(Paragraph(f'<b>Recommendation:</b> {flags.get("recommendation", "N/A")}', self.styles['Normal']))
		story.append(Spacer(1, 10))

		if flags.get('company_red_flags'):
			for f in flags.get('company_red_flags', []):
				color_style = self.styles['RiskHigh'] if f.get('severity') == 'high' else self.styles['Normal']
				story.append(Paragraph(f'⚠️ <b>{f.get("flag")}</b> ({f.get("severity")})', color_style))
				story.append(Paragraph(f'   <i>Verify by: {f.get("how_to_verify")}</i>', self.styles['Italic']))
				story.append(Spacer(1, 8))
		else:
			story.append(Paragraph('No major red flags detected.', self.styles['Normal']))

		story.append(Spacer(1, 20))

		# --- INTERVIEW CHEAT SHEET ---
		story.append(Paragraph('Interview Cheat Sheet', self.styles['SectionHeader']))

		story.append(Paragraph('<b>Questions to Ask:</b>', self.styles['Heading4']))
		for q in info.get('questions_to_ask', []):
			story.append(Paragraph(f'❓ {q}', self.styles['Normal']))
			story.append(Spacer(1, 4))

		story.append(Spacer(1, 10))
		story.append(Paragraph('<b>Tips from Candidates:</b>', self.styles['Heading4']))
		for t in insights.get('tips_from_candidates', []):
			story.append(Paragraph(f'💡 {t}', self.styles['Normal']))
			story.append(Spacer(1, 4))

		doc.build(story)
		return file_path


pdf_service = PDFService()

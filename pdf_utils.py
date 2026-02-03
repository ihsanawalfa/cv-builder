import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor
from pathlib import Path
import os
import json
import re
from datetime import datetime

def extract_resume_text(pdf_path):
    """Extract text content from a PDF resume."""
    text = ""
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")

def generate_pdf_from_json(tailored_resume_json, output_path=None):
    """
    Generate a PDF from a tailored resume JSON
    
    Args:
        tailored_resume_json: Path to JSON file or JSON object
        output_path: Path to save the PDF (if None, generates in output directory)
    
    Returns:
        Path to the generated PDF
    """
    # Load the JSON if a path is provided
    if isinstance(tailored_resume_json, str):
        with open(tailored_resume_json, 'r') as f:
            resume_data = json.load(f)
    else:
        resume_data = tailored_resume_json
    
    # Convert JSON to text format
    from resume_tailor import convert_json_to_text
    _, resume_text = convert_json_to_text(resume_data)
    
    # Generate output path if not provided
    if output_path is None:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"tailored_resume_{timestamp}.pdf"
    
    # Create PDF from text
    create_pdf_from_text(resume_text, output_path)
    
    return output_path

def create_pdf_from_text(text, output_path):
    """Create a modern, professional PDF resume document from text content."""
    # Modern resume colors
    primary_color = HexColor('#1A4D80')  # Professional dark blue
    secondary_color = HexColor('#60A3D9')  # Light blue for accents
    heading_color = HexColor('#0A3662')  # Dark blue for headings
    subheading_color = HexColor('#2E6287')  # Medium blue for subheadings
    text_color = HexColor('#333333')  # Dark gray for main text
    highlight_color = HexColor('#538BC5')  # Highlight blue
    
    # Document setup - optimized margins for single-page PDF
    doc = SimpleDocTemplate(
        str(output_path.absolute()),
        pagesize=letter,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.4*inch,
        bottomMargin=0.3*inch
    )
    
    # Get sample style sheet
    sample_style_sheet = getSampleStyleSheet()
    
    # Create custom styles dictionary
    styles = {}
    
    # Define custom styles - optimized for single-page PDF
    styles['Name'] = ParagraphStyle(
        'CustomName',
        parent=sample_style_sheet['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=19.8,
        leading=24.2,
        spaceAfter=3,
        textColor=heading_color,
        alignment=TA_LEFT,
    )
    
    styles['Contact'] = ParagraphStyle(
        'CustomContact',
        parent=sample_style_sheet['Normal'],
        fontName='Helvetica',
        fontSize=8.8,
        leading=12.1,
        spaceAfter=6,
        textColor=text_color,
        alignment=TA_LEFT,
    )
    
    styles['SectionHeading'] = ParagraphStyle(
        'CustomSectionHeading',
        parent=sample_style_sheet['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12.1,
        leading=14.3,
        spaceBefore=5,
        spaceAfter=4,
        textColor=heading_color,
        alignment=TA_LEFT,
        borderWidth=0,
        borderColor=primary_color,
        borderPadding=2,
    )
    
    styles['SubHeading'] = ParagraphStyle(
        'CustomSubHeading',
        parent=sample_style_sheet['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13.2,
        textColor=subheading_color,
        spaceBefore=3,
        spaceAfter=1,
    )
    
    styles['JobPeriod'] = ParagraphStyle(
        'CustomJobPeriod',
        parent=sample_style_sheet['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.8,
        leading=11,
        textColor=secondary_color,
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    
    styles['Skills'] = ParagraphStyle(
        'CustomSkills',
        parent=sample_style_sheet['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.8,
        leading=12.1,
        textColor=text_color,
        spaceAfter=3,
    )
    
    styles['SkillCategory'] = ParagraphStyle(
        'CustomSkillCategory',
        parent=sample_style_sheet['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.9,
        leading=12.1,
        textColor=subheading_color,
        spaceBefore=2,
        spaceAfter=1,
    )
    
    styles['Normal'] = ParagraphStyle(
        'CustomNormal',
        parent=sample_style_sheet['Normal'],
        fontName='Helvetica',
        fontSize=9.9,
        leading=13.2,
        textColor=text_color,
        spaceAfter=3,
    )
    
    styles['BulletPoint'] = ParagraphStyle(
        'CustomBulletPoint',
        parent=sample_style_sheet['Normal'],
        fontName='Helvetica',
        fontSize=9.9,
        leading=13.2,
        leftIndent=15,
        textColor=text_color,
        spaceAfter=2,
        bulletIndent=8,
    )
    
    # Process text into paragraphs
    flowables = []
    
    # Split text by lines and process
    lines = text.split('\n')
    section = "header"  # Start with header section
    current_paragraph = []
    bullet_points = []
    
    # Function to create a section header with underline - compact
    def add_section_header(title):
        flowables.append(Spacer(1, 3))
        # Add the section title
        flowables.append(Paragraph(title, styles['SectionHeading']))
        # Add an underline
        t = Table([['']], colWidths=[doc.width - 0.3*inch], rowHeights=[1])
        t.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ]))
        flowables.append(t)
        flowables.append(Spacer(1, 2))
    
    # Function to create clickable contact information
    def format_contact_info(text):
        parts = text.split(" | ")
        formatted_parts = []
        
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                # Make email clickable
                if key.lower() == "email":
                    formatted_parts.append(f"{key}: <a href='mailto:{value}' color='{primary_color.hexval()}'>{value}</a>")
                # Make github clickable
                elif key.lower() == "github":
                    formatted_parts.append(f"{key}: <a href='{value}' color='{primary_color.hexval()}'>{value}</a>")
                # Make linkedin clickable
                elif key.lower() == "linkedin":
                    formatted_parts.append(f"{key}: <a href='{value}' color='{primary_color.hexval()}'>{value}</a>")
                # Make telegram clickable
                elif key.lower() == "telegram":
                    formatted_parts.append(f"{key}: <a href='{value}' color='{primary_color.hexval()}'>{value}</a>")
                else:
                    formatted_parts.append(f"<b>{key}</b>: {value}")
            else:
                formatted_parts.append(part)
                
        return " | ".join(formatted_parts)
    
    # Function to process the current paragraph
    def process_current_paragraph():
        if not current_paragraph:
            return
            
        para_text = ' '.join(current_paragraph)
        
        # Process based on current section
        if section == "header":
            if len(current_paragraph) == 1 and len(para_text) < 50:
                # This is the name - make it stand out as H1
                flowables.append(Paragraph(para_text, styles['Name']))
            else:
                # This is contact info - make links clickable
                formatted_contact = format_contact_info(para_text)
                flowables.append(Paragraph(formatted_contact, styles['Contact']))
                
        elif section == "summary":
            # Format the summary with a bit more emphasis
            flowables.append(Paragraph(para_text, styles['Normal']))
            
        elif section == "experience":
            if len(para_text) < 50 and not para_text.startswith('Skills:') and not para_text.startswith('•'):
                if para_text.strip().lower().startswith(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")):
                    # This looks like a date period
                    flowables.append(Paragraph(para_text, styles['JobPeriod']))
                else:
                    # This looks like a job title - make it stand out
                    flowables.append(Paragraph(para_text, styles['SubHeading']))
            elif para_text.startswith('Skills:'):
                # Skills used in the job - format with bold emphasis
                skills_text = para_text.replace('Skills:', '<b>Skills:</b>')
                flowables.append(Paragraph(skills_text, styles['Skills']))
            elif para_text.startswith('•'):
                # Add to bullet points for later processing
                bullet_points.append(para_text[1:].strip())
            else:
                # Regular paragraph in experience section
                flowables.append(Paragraph(para_text, styles['Normal']))
                
        elif section == "skills":
            if ":" in para_text and len(para_text.split(":", 1)[0]) < 30:
                # This is a skill category
                category, skills = para_text.split(":", 1)
                flowables.append(Paragraph(f"<b>{category.strip()}</b>:", styles['SkillCategory']))
                
                # Format skills as a flowing list with commas
                skills_list = [s.strip() for s in skills.split(",")]
                skill_text = ", ".join(skills_list)
                flowables.append(Paragraph(skill_text, styles['Normal']))
            else:
                # Regular paragraph in skills section
                flowables.append(Paragraph(para_text, styles['Normal']))
                
        elif section == "education":
            if para_text.strip().lower().startswith(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")):
                # This looks like a date period
                flowables.append(Paragraph(para_text, styles['JobPeriod']))
            elif "degree" in para_text.lower() or "university" in para_text.lower() or "-" in para_text:
                # This looks like a degree/university line
                flowables.append(Paragraph(para_text, styles['SubHeading']))
            else:
                # Regular paragraph in education section
                flowables.append(Paragraph(para_text, styles['Normal']))
        else:
            # Default handling
            if len(para_text) < 50 and not para_text.startswith('•') and not para_text.startswith('-'):
                flowables.append(Paragraph(para_text, styles['SectionHeading']))
            else:
                flowables.append(Paragraph(para_text, styles['Normal']))
        
        flowables.append(Spacer(1, 2))  # Small spacer between paragraphs
    
    # Function to process bullet points as a list
    def process_bullet_points():
        if not bullet_points:
            return
            
        # Create a list of bullet points
        bullets = []
        for point in bullet_points:
            bullets.append(ListItem(Paragraph(point, styles['BulletPoint']), leftIndent=20))
        
        # Add the list to the flowables
        bullet_list = ListFlowable(
            bullets,
            bulletType='bullet',
            start=None,
            bulletFontSize=7.7,
            bulletFontName='Helvetica',
            leftIndent=15,
            bulletColor=highlight_color
        )
        flowables.append(bullet_list)
        flowables.append(Spacer(1, 3))
        
        # Clear the bullet points
        bullet_points.clear()
    
    # Create a separator line function - compact
    def add_separator():
        # Add a separator line
        t = Table([['']], colWidths=[doc.width - 0.3*inch], rowHeights=[1])
        t.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, secondary_color),
        ]))
        flowables.append(t)
        flowables.append(Spacer(1, 4))  # Space after separator
    
    for line in lines:
        line = line.strip()
        
        # Check for section headers
        if line.upper() == "SUMMARY":
            process_current_paragraph()
            process_bullet_points()
            current_paragraph = []
            add_section_header("SUMMARY")
            section = "summary"
            continue
        elif line.upper() == "EXPERIENCE":
            process_current_paragraph()
            process_bullet_points()
            current_paragraph = []
            add_section_header("EXPERIENCE")
            section = "experience"
            continue
        elif line.upper() == "SKILLS":
            process_current_paragraph()
            process_bullet_points()
            current_paragraph = []
            add_section_header("SKILLS")
            section = "skills"
            continue
        elif line.upper() == "EDUCATION":
            process_current_paragraph()
            process_bullet_points()
            current_paragraph = []
            add_section_header("EDUCATION")
            section = "education"
            continue
        elif line == "----":
            process_current_paragraph()
            process_bullet_points()
            current_paragraph = []
            add_separator()
            continue
            
        # Process regular lines
        if not line:  # Empty line indicates paragraph break
            process_current_paragraph()
            process_bullet_points()
            current_paragraph = []
        else:
            if line.startswith('•') and section == "experience":
                # Process any current paragraph before starting bullet points
                process_current_paragraph()
                current_paragraph = []
                # Add this bullet point
                bullet_points.append(line[1:].strip())
            else:
                # End any bullet list before continuing with regular paragraphs
                if bullet_points and not line.startswith('•'):
                    process_bullet_points()
                current_paragraph.append(line)
    
    # Handle any remaining paragraph and bullet points
    process_current_paragraph()
    process_bullet_points()
    
    # Build the PDF
    try:
        doc.build(flowables)
    except Exception as e:
        print(f"Error building PDF: {e}")
    
    return output_path
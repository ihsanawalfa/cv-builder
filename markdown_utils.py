import json
from datetime import datetime
from pathlib import Path
import os
from markdown_pdf import MarkdownPdf, Section
import re
from resume_tailor import convert_json_to_markdown

def generate_pdf_from_markdown(markdown_content, output_path=None):
    """
    Generate a PDF from markdown content
    
    Args:
        markdown_content: Markdown text to convert to PDF
        output_path: Path to save the PDF (if None, generates in output directory)
    
    Returns:
        Path to the generated PDF
    """
    # Generate output path if not provided
    if output_path is None:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"document_{timestamp}.pdf"
    
    # Create a temporary markdown file
    markdown_path = Path(str(output_path).replace('.pdf', '.md'))
    with open(markdown_path, 'w') as f:
        f.write(markdown_content)
    
    try:
        # Define CSS for styling - optimized for single-page PDF
        css = """
        @page {
            margin: 0.4in 0.5in 0.3in 0.5in;
            size: letter;
        }

        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            line-height: 1.3;
            color: #333333;
            font-size: 9pt;
            margin: 0;
            padding: 0;
        }

        a {
            color: #0066cc;
            text-decoration: none;
        }

        h1, h2, h3, h4 {
            color: #222222;
            margin-top: 0.4em;
            margin-bottom: 0.3em;
            line-height: 1.2;
        }

        h1 {
            font-size: 16pt;
            text-align: center;
        }

        h2 {
            font-size: 12pt;
            border-bottom: 1px solid #cccccc;
            padding-bottom: 0.1em;
        }

        h3 {
            font-size: 10pt;
        }

        p {
            margin-top: 0.2em;
            margin-bottom: 0.2em;
            line-height: 1.3;
        }

        ul {
            margin-top: 0.2em;
            margin-bottom: 0.2em;
            padding-left: 1.2em;
        }

        li {
            margin-bottom: 0.15em;
            line-height: 1.3;
        }

        blockquote {
            margin: 0.3em 0;
            padding-left: 0.5em;
            border-left: 2px solid #dddddd;
            color: #555555;
        }

        pre {
            background-color: #f5f5f5;
            padding: 0.3em;
            border-radius: 2px;
            overflow-x: auto;
            font-size: 8pt;
        }

        code {
            font-family: 'Courier New', monospace;
            background-color: #f5f5f5;
            padding: 1px 3px;
            border-radius: 2px;
            font-size: 8pt;
        }
        """
        
        # Generate PDF from markdown
        pdf = MarkdownPdf(toc_level=2)
        pdf.add_section(Section(markdown_content, toc=False), user_css=css)
        pdf.meta["title"] = "Document"
        pdf.meta["author"] = "Resumer Application"

        pdf.save(output_path)
            
        return output_path
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise

def generate_pdf_from_json(tailored_resume_json, output_path=None):
    """
    Generate a PDF from a tailored resume JSON using markdown
    
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
    
    # Convert JSON to markdown format
    markdown_content = convert_json_to_markdown(resume_data)
    
    # Generate output path if not provided
    if output_path is None:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"tailored_resume_{timestamp}.pdf"
    
    # Create a temporary markdown file
    markdown_path = Path(str(output_path).replace('.pdf', '.md'))
    with open(markdown_path, 'w') as f:
        f.write(markdown_content)
    
    # Convert markdown to PDF
    try:
        # Define CSS for styling - optimized for single-page PDF
        css = """
        :root {
            --primary-color: #0A3662;
            --secondary-color: #0366d6;
            --text-color: #333333;
            --light-gray: #666666;
            --border-color: #dddddd;
        }

        @page {
            margin: 0.4in 0.5in 0.3in 0.5in;
            size: letter;
        }

        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            line-height: 1.3;
            color: var(--text-color);
            font-size: 9pt;
            margin: 0;
            padding: 0;
        }

        /* Center text alignment */
        .text-center {
            text-align: center;
        }

        /* Header styling - reduced sizes */
        h1 {
            font-size: 18pt;
            color: var(--primary-color);
            margin-top: 0;
            margin-bottom: 0.2em;
            font-weight: bold;
            text-align: center;
            line-height: 1.2;
        }

        h2 {
            font-size: 11pt;
            color: var(--primary-color);
            border-bottom: 1px solid var(--primary-color);
            padding-bottom: 0.1em;
            margin-top: 0.4em;
            margin-bottom: 0.3em;
            line-height: 1.2;
        }

        h3 {
            font-size: 10pt;
            color: var(--primary-color);
            margin: 0.3em 0 0.2em 0;
            line-height: 1.2;
        }

        /* Links */
        a {
            color: var(--secondary-color);
            text-decoration: none;
        }

        /* Text styling - reduced margins */
        p {
            margin: 0.2em 0;
            line-height: 1.3;
        }

        em {
            font-style: italic;
            color: var(--light-gray);
        }

        strong {
            font-weight: bold;
        }

        /* Summary section - compact */
        .summary {
            border-left: 2px solid var(--primary-color);
            padding-left: 0.5em;
            margin: 0.3em 0;
        }

        /* Experience section - reduced spacing */
        .experience-entry {
            margin-bottom: 0.5em;
        }

        .job-title {
            color: var(--primary-color);
            margin-bottom: 0.2em;
        }

        .job-meta {
            color: var(--light-gray);
            margin: 0.1em 0;
        }

        .job-location {
            font-weight: 500;
        }

        /* List styling - compact */
        ul {
            margin: 0.2em 0;
            padding-left: 1.2em;
        }

        li {
            margin-bottom: 0.15em;
            line-height: 1.3;
        }

        /* Skills section - compact */
        .skills-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5em;
            margin: 0.3em 0;
        }

        .skill-category {
            border: 1px solid var(--border-color);
            padding: 0.3em;
            border-radius: 2px;
        }

        /* Contact section - compact */
        .contact-links {
            display: flex;
            justify-content: center;
            margin: 0.3em 0;
        }

        .contact-link {
            margin: 0 8px;
        }
        """
        
        # Extract name from resume data for PDF metadata
        print('resumedata =', resume_data)
        name = "Resume"
        author = "Unknown"
        if "name" in resume_data:
            name = f"Resume - {resume_data['name']}"
            author = resume_data['name']
        
        # Generate PDF from markdown
        pdf = MarkdownPdf(toc_level=3)
        pdf.add_section(Section(markdown_content, toc=False), user_css=css)
        pdf.meta["title"] = name
        pdf.meta["author"] = author

        pdf.save(output_path)

        # Keep the temporary markdown file for debugging
        # (You can uncomment the code below to delete it if needed)
        # if markdown_path.exists():
        #     os.remove(markdown_path)
            
        return output_path
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise
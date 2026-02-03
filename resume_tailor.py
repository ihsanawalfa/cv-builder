import json
from datetime import datetime
from pathlib import Path
import os
import re

def convert_markdown_bold_to_html(data):
    """
    Recursively convert markdown **bold** syntax to HTML <strong> tags
    in all string values of a dictionary or list.
    """
    if isinstance(data, dict):
        return {key: convert_markdown_bold_to_html(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_markdown_bold_to_html(item) for item in data]
    elif isinstance(data, str):
        # Convert **text** to <strong>text</strong>
        # Handle multiple bold sections in the same string
        text = data
        # Pattern to match **text** but not **text**text** (greedy match)
        # Use non-greedy matching to handle multiple bold sections
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        return text
    else:
        return data

def enforce_career_progression(resume_data):
    """
    Ensure job titles show logical career progression:
    - First (most recent) = Senior/Lead level
    - Middle = Mid-level (no Senior prefix)
    - Last (oldest) = Entry level
    """
    if "experience" not in resume_data or not isinstance(resume_data["experience"], list):
        return resume_data
    
    experiences = resume_data["experience"]
    if len(experiences) < 2:
        return resume_data  # Need at least 2 experiences to enforce progression
    
    # Extract domain from job titles (e.g., "Shopify", "iOS", "Full Stack")
    def extract_domain(title):
        """Extract the domain/technology from job title"""
        title_lower = title.lower()
        # Common domains
        domains = ["shopify", "ios", "android", "react", "angular", "vue", "node", "python", 
                   "java", "full stack", "frontend", "backend", "devops", "cloud"]
        for domain in domains:
            if domain in title_lower:
                return domain.title() if domain != "full stack" else "Full Stack"
        return None
    
    # Get domain from first experience (most recent)
    first_title = experiences[0].get("title", "")
    domain = extract_domain(first_title)
    
    # If we can't extract domain, try to infer from common patterns
    if not domain:
        # Check if title contains "Senior" or "Lead"
        if "senior" in first_title.lower() or "lead" in first_title.lower():
            # Try to extract what comes after "Senior" or "Lead"
            parts = first_title.split()
            for i, part in enumerate(parts):
                if part.lower() in ["senior", "lead", "principal"] and i + 1 < len(parts):
                    domain = " ".join(parts[i+1:])
                    break
    
    # If still no domain, use a generic approach
    if not domain:
        # Remove common prefixes and use the rest
        title_clean = first_title
        for prefix in ["Senior", "Lead", "Principal", "Junior"]:
            title_clean = title_clean.replace(prefix, "").strip()
        domain = title_clean if title_clean else "Developer"
    
    # Enforce progression
    num_experiences = len(experiences)
    
    # First (most recent) - should be Senior/Lead
    first_title = experiences[0].get("title", "")
    if not any(word.lower() in first_title.lower() for word in ["Senior", "Lead", "Principal", "Staff"]):
        # Add Senior prefix if not present
        if domain:
            experiences[0]["title"] = f"Senior {domain} Developer" if "Developer" not in domain else f"Senior {domain}"
        else:
            experiences[0]["title"] = f"Senior {first_title}"
    
    # Last (oldest) - should be entry level
    if num_experiences >= 2:
        last_title = experiences[-1].get("title", "")
        # Remove Senior/Lead if present
        last_title_clean = last_title
        for prefix in ["Senior", "Lead", "Principal", "Staff"]:
            if prefix.lower() in last_title_clean.lower():
                last_title_clean = last_title_clean.replace(prefix, "").strip()
                break
        
        # If it still looks senior, make it entry level
        if any(word.lower() in last_title_clean.lower() for word in ["Senior", "Lead", "Principal"]):
            if domain:
                experiences[-1]["title"] = f"{domain} Developer" if "Developer" not in domain else domain
            else:
                experiences[-1]["title"] = last_title_clean
        else:
            experiences[-1]["title"] = last_title_clean
    
    # Middle experiences - should be mid-level (no Senior)
    for i in range(1, num_experiences - 1):
        mid_title = experiences[i].get("title", "")
        # Remove Senior/Lead if present
        for prefix in ["Senior", "Lead", "Principal", "Staff"]:
            if prefix.lower() in mid_title.lower():
                mid_title_clean = mid_title.replace(prefix, "").strip()
                if domain and domain.lower() not in mid_title_clean.lower():
                    experiences[i]["title"] = f"{domain} Developer" if "Developer" not in domain else domain
                else:
                    experiences[i]["title"] = mid_title_clean
                break
    
    return resume_data

def tailor_resume(job_description, model, template = "resume_templates/michael.json"):
    """
    Tailor the resume based on the job description
    Uses the template resume JSON and creates a tailored version
    """
    # Load the template resume
    template_path = os.path.join(os.path.dirname(__file__), template)
    with open(template_path, "r") as f:
        resume_structure = json.load(f)
    
    # Create the tailoring prompt
    tailoring_prompt = f"""
    I need to tailor my resume for a specific job. I'll provide my current resume structure in JSON format and the job description.
    
    JOB DESCRIPTION:
    {job_description}
    
    MY CURRENT RESUME (in JSON format):
    {json.dumps(resume_structure, indent=2)}
    
    Based on the job description, please create a tailored version of my resume by modifying the following sections:
    
    1. Summary: Rewrite to emphasize skills and experiences relevant to this specific job
       - Use <strong>bold</strong> formatting for technical skills (e.g. <strong>JavaScript</strong>, <strong>Python</strong>, <strong>AWS</strong>, etc)
       - Make the summary concise and focused on the job requirements
    
    2. Experience: For each experience entry (IMPORTANT - maintain career progression):
       - Keep the company name and period the same
       - CRITICAL: Maintain logical career progression in job titles based on chronological order:
         * The FIRST job in the list (most recent) should be SENIOR/LEAD level (e.g., "Senior Developer", "Lead Developer")
         * The MIDDLE job should be MID-LEVEL (without "Senior" prefix, e.g., "Developer", "Engineer", "Full Stack Developer")
         * The LAST job in the list (oldest) should be ENTRY level (e.g., "Web Developer", "Junior Developer", "Frontend Developer" without "Senior")
       - Adjust job titles to match the job description's DOMAIN (e.g., if job is for Shopify, use "Shopify Developer" not "Frontend Developer")
       - BUT maintain the level progression based on chronological order:
         * Most recent (first): "Senior [Domain] Developer" or "Lead [Domain] Developer"
         * Middle: "[Domain] Developer" or "[Domain] Engineer" (no "Senior" prefix)
         * Oldest (last): "Web Developer", "[Domain] Developer", or "Junior [Domain] Developer" (entry level)
       - Example progression for Shopify: "Senior Shopify Developer" → "Shopify Developer" → "Web Developer"
       - Example progression for iOS: "Senior iOS Developer" → "iOS Developer" → "Mobile Developer" or "Junior iOS Developer"
       - Example progression for Full Stack: "Senior Full Stack Developer" → "Full Stack Developer" → "Web Developer"
       - DO NOT make all titles "Senior" - only the most recent position should be senior level
       - Tailor the summary to match the job description, to highlight relevant achievements, using markdown for technical terms
       - The 'highlights' section is optional
       - If you include highlights, use markdown to bold important technical terms
       - re-write and tailor each highlight to better match the job requirements
       - Adjust the skills to match the job requirements (add or remove skills as needed)
    
    3. Skills: Reorganize and emphasize skills relevant to the job
       - Prioritize skills mentioned in the job description
       - Filter out unrelevant skills
       - Keep the same structure but adjust the content
    
    Do NOT modify:
    - Name and contact information
    - Company names and dates
    - Education section structure
    
    CRITICAL FORMATTING RULES:
    - Use ONLY HTML <strong>bold</strong> tags for all technical terms and skills (like <strong>JavaScript</strong>, <strong>Python</strong>, <strong>AWS</strong>, etc)
    - DO NOT use markdown **bold** syntax (no asterisks)
    - DO NOT use double asterisks (**) anywhere in the text
    - All bold text must use <strong>text</strong> HTML format only
    
    CRITICAL CAREER PROGRESSION RULE:
    - Job titles MUST show career progression from entry-level to senior
    - Most recent job (first in list) = Senior/Lead level
    - Middle job = Mid-level (no "Senior" prefix)
    - Oldest job (last in list) = Entry-level (can use "Junior" or just domain-specific title without "Senior")
    - NEVER make all job titles the same level (e.g., all "Senior Developer")
    
    Return ONLY a JSON object with the same structure as the input but with tailored content. 
    Do not include any explanations or additional text outside the JSON.
    """
    
    response = model.generate_content(tailoring_prompt)
    
    try:
        # Attempt to parse the response as JSON
        # Extract JSON if it's wrapped in markdown code blocks
        text = response.text
        if '```json' in text and '```' in text.split('```json', 1)[1]:
            json_str = text.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '```' in text and '```' in text.split('```', 1)[1]:
            json_str = text.split('```', 1)[1].split('```', 1)[0].strip()
        else:
            json_str = text
            
        tailored_resume = json.loads(json_str)
        
        # Enforce career progression in job titles
        tailored_resume = enforce_career_progression(tailored_resume)
        
        # Convert any markdown **bold** syntax to HTML <strong> tags
        tailored_resume = convert_markdown_bold_to_html(tailored_resume)
        
        # Save the tailored resume to a file
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file_path = output_dir / f"tailored_resume_{timestamp}.json"
        
        with open(json_file_path, "w") as f:
            json.dump(tailored_resume, f, indent=2)
            
        return json_file_path, tailored_resume
    
    except json.JSONDecodeError:
        # If JSON parsing fails, save the raw text
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_file_path = output_dir / f"tailored_resume_raw_{timestamp}.txt"
        
        with open(raw_file_path, "w") as f:
            f.write(response.text)
            
        raise Exception(f"Failed to parse tailored resume as JSON. Raw output saved to {raw_file_path}")

def convert_json_to_text(tailored_resume_json):
    """
    Convert the tailored resume JSON to a formatted text
    This can be used for later PDF generation
    """
    # Convert the resume JSON to formatted text
    if isinstance(tailored_resume_json, str):
        # If path is provided, load the JSON
        with open(tailored_resume_json, "r") as f:
            tailored_resume = json.load(f)
    else:
        # If the JSON object is provided directly
        tailored_resume = tailored_resume_json
    
    # Convert to text format
    text_content = []
    
    # Add name and contact information
    text_content.append(tailored_resume["name"])
    
    # Add contact information as separate lines
    contact = tailored_resume["contact"]
    for key, value in contact.items():
        text_content.append(f"{key}: {value}")
    
    # Add separator
    text_content.append("----")
    
    # Add summary
    text_content.append("SUMMARY")
    text_content.append(tailored_resume["summary"])
    text_content.append("")
    
    # Add references if they exist
    if "references" in tailored_resume and tailored_resume["references"]:
        text_content.append("PROFESSIONAL REFERENCES")
        for ref in tailored_resume["references"]:
            text_content.append(f"{ref.get('name', '')} - Link: {ref.get('link', '')}")
        text_content.append("")
    
    # Add experience
    text_content.append("EXPERIENCE")
    
    for exp in tailored_resume["experience"]:
        # Title and company
        title_company = f"{exp.get('title', '')} at {exp.get('company', '')}"
        text_content.append(title_company)
        
        # Period
        if "period" in exp:
            text_content.append(exp["period"])
        
        # Skills used
        if "skills" in exp and exp["skills"]:
            if isinstance(exp["skills"], list):
                text_content.append("Skills: " + ", ".join(exp["skills"]))
            else:
                text_content.append(f"Skills: {exp['skills']}")
        
        # Summary
        if "summary" in exp:
            text_content.append(exp["summary"])
        
        # Highlights/bullet points
        if "highlights" in exp and exp["highlights"]:
            for highlight in exp["highlights"]:
                text_content.append(f"• {highlight}")
        
        text_content.append("")
    
    # Add skills section - Removed per user request
    # text_content.append("SKILLS")
    # 
    # skills = tailored_resume["skills"]
    # if isinstance(skills, dict):
    #     for category, skill_list in skills.items():
    #         if isinstance(skill_list, list):
    #             text_content.append(f"{category}: {', '.join(skill_list)}")
    #         else:
    #             text_content.append(f"{category}: {skill_list}")
    # elif isinstance(skills, list):
    #     text_content.append(", ".join(skills))
    # else:
    #     text_content.append(skills)
    # 
    # text_content.append("")
    
    # Add education
    text_content.append("EDUCATION")
    
    education = tailored_resume["education"]
    if isinstance(education, dict):
        text_content.append(f"{education.get('degree', '')} - {education.get('university', '')}")
        if "period" in education:
            text_content.append(education["period"])
        if "description" in education:
            text_content.append(education["description"])
    elif isinstance(education, list):
        for edu in education:
            if isinstance(edu, dict):
                text_content.append(f"{edu.get('degree', '')} - {edu.get('university', '')}")
                if "period" in edu:
                    text_content.append(edu["period"])
                if "description" in edu:
                    text_content.append(edu["description"])
            else:
                text_content.append(edu)
    else:
        text_content.append(education)
    
    # Combine all text
    full_text = "\n".join(text_content)
    
    # Save the text version
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    text_file_path = output_dir / f"tailored_resume_text_{timestamp}.txt"
    
    with open(text_file_path, "w") as f:
        f.write(full_text)
    
    return text_file_path, full_text

def convert_json_to_markdown(tailored_resume_json):
    """
    Convert the tailored resume JSON to a well-formatted markdown
    This is used for PDF generation with styling
    Uses the template files in the output_template directory
    """
    # Load the JSON if a path is provided
    if isinstance(tailored_resume_json, str):
        with open(tailored_resume_json, "r") as f:
            tailored_resume = json.load(f)
    else:
        tailored_resume = tailored_resume_json
    
    # Load the main template file
    template_dir = os.path.join(os.path.dirname(__file__), "output_template")
    template_path = os.path.join(os.path.dirname(__file__), "output_template.md")
    try:
        with open(template_path, "r") as f:
            template_content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Resume template markdown file not found at {template_path}")
    
    # Load all section templates
    def load_template(filename):
        file_path = os.path.join(template_dir, filename)
        with open(file_path, "r") as f:
            return f.read()
    
    top_section_template = load_template("top_section.md")
    summary_section_template = load_template("summary_section.md")
    references_section_template = load_template("references_section.md")
    reference_item_template = load_template("reference_item.md")
    experiences_section_template = load_template("experiences_section.md")
    experience_item_template = load_template("experience_item.md")
    experience_highlights_template = load_template("experience_highlights.md")
    experience_highlight_item_template = load_template("experience_highlight_item.md")
    skills_section_template = load_template("skills_section.md")
    skill_section_item_template = load_template("skill_section_item.md")
    education_section_template = load_template("education_section.md")
    
    # Generate Top Section
    contact = tailored_resume["contact"]
    name = tailored_resume["name"]
    
    # Generate contact links HTML - display actual email addresses and URLs
    contact_links = []
    for key, value in contact.items():
        if key != "location":  # Skip location as it's displayed separately
            # Extract display text: for mailto: extract email, for tel: extract phone, otherwise use full URL
            if value.startswith("mailto:"):
                display_text = value.replace("mailto:", "")
            elif value.startswith("tel:"):
                display_text = value.replace("tel:", "")
            else:
                display_text = value
            contact_links.append(f'<a href="{value}" style="margin: 0 0.5em; color: #0366d6; text-decoration: underline;">{display_text}</a>')
    
    contacts_html = " • ".join(contact_links)
    
    top_section = top_section_template
    top_section = top_section.replace("{{name}}", name)
    
    # Load and include location section only if it exists in contact
    location_section_template = load_template("location_section.md")
    location_section = ""
    if "location" in contact and contact["location"]:
        location = contact["location"]
        location_section = location_section_template.replace("{{location}}", location)
    
    top_section = top_section.replace("{{location_section}}", location_section)
    top_section = top_section.replace("{{contacts}}", contacts_html)
    
    # Generate Summary Section
    summary = tailored_resume["summary"]
    summary_section = summary_section_template.replace("{{summary}}", summary)
    
    # Generate Experiences Section
    experiences = ""
    for exp in tailored_resume["experience"]:
        # Extract information
        title = exp.get('title', '')
        company = exp.get('company', '')
        
        # Parse location from company string if it's in parentheses
        location = ""
        if "(" in company and ")" in company:
            company_parts = company.split("(", 1)
            company = company_parts[0].strip()
            location = company_parts[1].replace(")", "").strip()
        
        # Extract period and split into from/to
        period = exp.get('period', '')
        from_date = period
        to_date = ""
        if "-" in period:
            date_parts = period.split("-", 1)
            from_date = date_parts[0].strip()
            to_date = date_parts[1].strip()
        
        # Get summary and skills
        description = exp.get('summary', '')
        skills_text = ""
        if "skills" in exp and exp["skills"]:
            if isinstance(exp["skills"], list):
                skills_text = ", ".join(exp["skills"])
            else:
                skills_text = str(exp["skills"])
        
        # Generate highlights section if needed
        highlights_html = ""
        highlights = exp.get('highlights', [])
        if highlights and any(h.strip() for h in highlights):
            highlight_items = ""
            for highlight in highlights:
                if highlight and highlight.strip():
                    highlight_item = experience_highlight_item_template.replace("{{highlight}}", highlight)
                    highlight_items += highlight_item
            
            highlights_html = experience_highlights_template.replace("{{highlights}}", highlight_items)
        
        # Create experience item by replacing placeholders
        experience_item = experience_item_template
        experience_item = experience_item.replace("{{position}}", title)
        experience_item = experience_item.replace("{{company_name}}", company)
        experience_item = experience_item.replace("{{location}}", location)
        experience_item = experience_item.replace("{{from}}", from_date)
        experience_item = experience_item.replace("{{to}}", to_date)
        experience_item = experience_item.replace("{{description}}", description)
        experience_item = experience_item.replace("{{skills}}", skills_text)
        experience_item = experience_item.replace("{{highlights}}", highlights_html)
        
        experiences += experience_item + "\n"
    
    # Combine experiences into the experiences section
    experiences_section = experiences_section_template.replace("{{experiences}}", experiences)
    
    # Generate Skills Section - Removed per user request
    # skills = tailored_resume["skills"]
    # skills_html = ""
    # if isinstance(skills, dict):
    #     for category, skill_list in skills.items():
    #         if isinstance(skill_list, list):
    #             skills_text = ", ".join(skill_list)
    #         else:
    #             skills_text = str(skill_list)
    #         
    #         skill_item = skill_section_item_template
    #         skill_item = skill_item.replace("{{category}}", category)
    #         skill_item = skill_item.replace("{{skills}}", skills_text)
    #         skills_html += skill_item + "\n"
    # 
    # skills_section = skills_section_template.replace("{{skills}}", skills_html)
    
    # Set skills section to empty string to remove it from PDF
    skills_section = ""
    
    # Generate Education Section
    # For now, using the template directly since it has fixed values
    # In a future enhancement, we could make this dynamic too
    education_section = education_section_template
    if isinstance(tailored_resume["education"], dict):
        education = tailored_resume["education"]
        degree = education.get("degree", "Bachelor of Information Technology")
        university = education.get("university", "James Cook University, Singapore")
        period = education.get("period", "Jan 2009 - Dec 2011")
        description = education.get("description", "Major concentration in Software Development, Algorithm Design, and Database Management Systems with distinction.")
        
        # Replace education information if different from defaults
        education_section = education_section.replace("{{degree}}", degree)
        education_section = education_section.replace("{{university}}", university)
        education_section = education_section.replace("{{period}}", period)
        education_section = education_section.replace("{{description}}", description)
    
    # Generate References Section (only if references exist and not empty)
    references_section = ""
    if "references" in tailored_resume and tailored_resume["references"]:
        references_html = ""
        for ref in tailored_resume["references"]:
            ref_item = reference_item_template
            ref_item = ref_item.replace("{{name}}", ref.get("name", ""))
            ref_item = ref_item.replace("{{text}}", ref.get("text", ""))
            ref_item = ref_item.replace("{{link}}", ref.get("link", "#"))
            references_html += ref_item
        
        references_section = references_section_template.replace("{{references}}", references_html)
    
    # Combine all sections into the main template
    template_content = template_content.replace("{{top_section}}", top_section)
    template_content = template_content.replace("{{summary_section}}", summary_section)
    template_content = template_content.replace("{{references_section}}", references_section)
    template_content = template_content.replace("{{experiences_section}}", experiences_section)
    template_content = template_content.replace("{{skills_section}}", skills_section)
    template_content = template_content.replace("{{education_section}}", education_section)
    
    # Save the markdown version
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    markdown_file_path = output_dir / f"tailored_resume_markdown_{timestamp}.md"
    
    with open(markdown_file_path, "w") as f:
        f.write(template_content)
    
    return template_content
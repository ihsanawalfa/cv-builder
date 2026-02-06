import json
from datetime import datetime
from pathlib import Path
import os
import re

def fix_repetitive_verbs(resume_data):
    """
    Fix repetitive action verbs in experience highlights and summary
    Ensures no verb is used more than 2 times across the entire resume
    """
    if "experience" not in resume_data or not isinstance(resume_data["experience"], list):
        return resume_data
    
    # Common action verbs and their alternatives (expanded list)
    verb_alternatives = {
        "architected": ["engineered", "designed", "built", "constructed", "developed", "crafted", "established", "pioneered"],
        "architecting": ["engineering", "designing", "building", "constructing", "developing", "crafting"],
        "developed": ["architected", "engineered", "built", "designed", "created", "implemented", "delivered", "constructed", "established", "pioneered"],
        "developing": ["architecting", "engineering", "building", "designing", "creating", "implementing", "delivering"],
        "optimized": ["enhanced", "streamlined", "improved", "refined", "upgraded", "boosted", "maximized"],
        "created": ["established", "founded", "built", "designed", "launched", "pioneered", "initiated", "introduced"],
        "implemented": ["deployed", "integrated", "executed", "established", "introduced", "rolled out", "delivered"],
        "built": ["architected", "engineered", "constructed", "developed", "designed", "crafted", "assembled"],
        "designed": ["architected", "crafted", "created", "engineered", "planned", "conceptualized", "modeled"],
        "led": ["spearheaded", "orchestrated", "managed", "directed", "headed", "guided", "championed"],
        "managed": ["orchestrated", "supervised", "coordinated", "oversaw", "directed", "administered", "governed"],
        "improved": ["enhanced", "optimized", "upgraded", "refined", "boosted", "elevated", "advanced"],
        "increased": ["boosted", "enhanced", "amplified", "expanded", "scaled", "multiplied", "accelerated"],
        "reduced": ["minimized", "decreased", "lowered", "cut", "slashed", "diminished", "curtailed"],
        "collaborated": ["partnered", "worked with", "cooperated", "teamed up", "joined forces"],
        "delivered": ["executed", "completed", "achieved", "accomplished", "realized", "fulfilled"]
    }
    
    # Track verb usage across summary and all experience
    verb_counts = {}
    all_text_items = []
    
    # Check summary
    if "summary" in resume_data and isinstance(resume_data["summary"], str):
        all_text_items.append(("summary", resume_data["summary"]))
    
    # Collect all highlights
    for exp in resume_data["experience"]:
        if "highlights" in exp and isinstance(exp["highlights"], list):
            for highlight in exp["highlights"]:
                all_text_items.append((exp, highlight))
        # Also check experience summary
        if "summary" in exp and isinstance(exp["summary"], str):
            all_text_items.append((exp, exp["summary"]))
    
    # Count verb usage using regex for whole word matching (avoid double counting)
    import re
    for source, text in all_text_items:
        if isinstance(text, str):
            text_lower = text.lower()
            # Count each verb using whole word boundary matching (only count once per text item)
            for verb_key in verb_alternatives.keys():
                pattern = r'\b' + re.escape(verb_key) + r'\b'
                matches = re.findall(pattern, text_lower)
                if matches:
                    verb_counts[verb_key] = verb_counts.get(verb_key, 0) + len(matches)
    
    # Fix overused verbs (used more than 2 times)
    for verb, count in verb_counts.items():
        if count > 2:
            alternatives = verb_alternatives.get(verb, [])
            if alternatives:
                replacement_count = 0
                needed_replacements = count - 2
                
                # Create a list to track which items we've processed
                processed_items = []
                
                for source, text in all_text_items:
                    if isinstance(text, str) and replacement_count < needed_replacements:
                        text_lower = text.lower()
                        pattern = r'\b' + re.escape(verb) + r'\b'
                        
                        # Check if verb exists in this text
                        if re.search(pattern, text_lower):
                            # Replace only the first occurrence in this text (to avoid replacing multiple times in same text)
                            def replace_first(match):
                                nonlocal replacement_count
                                if replacement_count < needed_replacements:
                                    alt_verb = alternatives[replacement_count % len(alternatives)]
                                    replacement_count += 1
                                    # Preserve capitalization
                                    matched = match.group()
                                    if matched and matched[0].isupper():
                                        return alt_verb.capitalize()
                                    return alt_verb
                                return match.group()
                            
                            # Replace first occurrence only
                            new_text = re.sub(pattern, replace_first, text, count=1, flags=re.IGNORECASE)
                            
                            if new_text != text:
                                if source == "summary":
                                    resume_data["summary"] = new_text
                                    # Update the text in all_text_items for subsequent checks
                                    for idx, (s, t) in enumerate(all_text_items):
                                        if s == "summary" and t == text:
                                            all_text_items[idx] = ("summary", new_text)
                                            break
                                elif isinstance(source, dict):
                                    # Find and update the highlight or summary
                                    if "highlights" in source and text in source["highlights"]:
                                        highlight_index = source["highlights"].index(text)
                                        source["highlights"][highlight_index] = new_text
                                        # Update in all_text_items
                                        for idx, (s, t) in enumerate(all_text_items):
                                            if s == source and t == text and "highlights" in source:
                                                all_text_items[idx] = (source, new_text)
                                                break
                                    elif "summary" in source and source["summary"] == text:
                                        source["summary"] = new_text
                                        # Update in all_text_items
                                        for idx, (s, t) in enumerate(all_text_items):
                                            if s == source and t == text and "summary" in source:
                                                all_text_items[idx] = (source, new_text)
                                                break
    
    # Also fix duplicate words in the same sentence (e.g., "Architected and architected")
    # This handles cases where the same verb appears twice in one bullet point
    verb_alternatives_for_duplicates = {
        "architected": ["engineered", "designed", "built", "constructed"],
        "architecting": ["engineering", "designing", "building", "constructing"],
        "developed": ["engineered", "built", "designed", "created"],
        "designed": ["architected", "crafted", "created", "engineered"],
        "built": ["architected", "engineered", "constructed", "developed"],
        "created": ["established", "built", "designed", "launched"],
        "implemented": ["deployed", "integrated", "executed", "established"],
    }
    
    for exp in resume_data.get("experience", []):
        if "highlights" in exp and isinstance(exp["highlights"], list):
            for i, highlight in enumerate(exp["highlights"]):
                if isinstance(highlight, str):
                    # Find duplicate words (case-insensitive, whole word matching)
                    words = highlight.split()
                    fixed_words = []
                    seen_words_lower = {}
                    for j, word in enumerate(words):
                        word_lower = word.lower()
                        # Remove punctuation for comparison
                        word_clean = re.sub(r'[^\w]', '', word_lower)
                        if word_clean and word_clean in seen_words_lower:
                            # This is a duplicate - replace with alternative
                            alternatives = verb_alternatives_for_duplicates.get(word_clean, ["engineered", "designed", "built"])
                            alt = alternatives[0]  # Use first alternative
                            # Preserve capitalization
                            if word and word[0].isupper():
                                alt = alt.capitalize()
                            fixed_words.append(alt)
                        else:
                            seen_words_lower[word_clean] = j
                            fixed_words.append(word)
                    if len(fixed_words) == len(words) and fixed_words != words:
                        exp["highlights"][i] = ' '.join(fixed_words)
        # Also check experience summary
        if "summary" in exp and isinstance(exp["summary"], str):
            words = exp["summary"].split()
            fixed_words = []
            seen_words_lower = {}
            for j, word in enumerate(words):
                word_lower = word.lower()
                word_clean = re.sub(r'[^\w]', '', word_lower)
                if word_clean and word_clean in seen_words_lower:
                    alternatives = verb_alternatives_for_duplicates.get(word_clean, ["engineered", "designed", "built"])
                    alt = alternatives[0]
                    if word and word[0].isupper():
                        alt = alt.capitalize()
                    fixed_words.append(alt)
                else:
                    seen_words_lower[word_clean] = j
                    fixed_words.append(word)
            if len(fixed_words) == len(words) and fixed_words != words:
                exp["summary"] = ' '.join(fixed_words)
    
    return resume_data

def remove_buzzwords(resume_data):
    """
    Remove or replace common buzzwords and clichés from resume
    Based on Resume Worded analysis
    """
    # Common buzzwords to avoid (with replacements)
    buzzword_replacements = {
        "self-starter": "proactive professional",
        "self starter": "proactive professional",
        "attention to detail": "meticulous approach",
        "problem-solving": "analytical thinking",
        "problem solving": "analytical thinking",
        "proven track record": "demonstrated success",
        "proven track": "demonstrated",
        "team player": "collaborative professional",
        "hard worker": "dedicated professional",
        "go-getter": "results-driven",
        "think outside the box": "innovative approach",
        "synergy": "collaboration",
        "leverage": "utilize" or "use",
        "utilize": "use",
        "action-oriented": "results-driven",
        "detail-oriented": "meticulous",
        "passionate": "committed" or "dedicated",
        "rockstar": "expert",
        "ninja": "specialist",
        "guru": "expert"
    }
    
    # Remove buzzwords from summary
    if "summary" in resume_data and isinstance(resume_data["summary"], str):
        summary = resume_data["summary"]
        for buzzword, replacement in buzzword_replacements.items():
            # Case-insensitive replacement
            import re
            pattern = r'\b' + re.escape(buzzword) + r'\b'
            summary = re.sub(pattern, replacement, summary, flags=re.IGNORECASE)
        resume_data["summary"] = summary
    
    # Remove buzzwords from experience summaries
    if "experience" in resume_data and isinstance(resume_data["experience"], list):
        for exp in resume_data["experience"]:
            if "summary" in exp and isinstance(exp["summary"], str):
                exp_summary = exp["summary"]
                for buzzword, replacement in buzzword_replacements.items():
                    import re
                    pattern = r'\b' + re.escape(buzzword) + r'\b'
                    exp_summary = re.sub(pattern, replacement, exp_summary, flags=re.IGNORECASE)
                exp["summary"] = exp_summary
            
            # Remove buzzwords from highlights
            if "highlights" in exp and isinstance(exp["highlights"], list):
                for i, highlight in enumerate(exp["highlights"]):
                    if isinstance(highlight, str):
                        for buzzword, replacement in buzzword_replacements.items():
                            import re
                            pattern = r'\b' + re.escape(buzzword) + r'\b'
                            highlight = re.sub(pattern, replacement, highlight, flags=re.IGNORECASE)
                        exp["highlights"][i] = highlight
    
    # Remove buzzwords from skills section (especially soft skills)
    if "skills" in resume_data:
        skills = resume_data["skills"]
        if isinstance(skills, dict):
            # Check soft skills category
            for category in ["Soft Skills", "soft_skills", "Soft skills"]:
                if category in skills and isinstance(skills[category], list):
                    # Remove buzzword skills
                    skills[category] = [
                        skill for skill in skills[category] 
                        if skill.lower() not in ["self-starter", "attention to detail", "problem-solving", "team player", "hard worker"]
                    ]
                    # If category becomes empty, remove it
                    if not skills[category]:
                        del skills[category]
        elif isinstance(skills, list):
            # Remove buzzword skills from flat list
            buzzword_skills = ["self-starter", "attention to detail", "problem-solving", "team player", "hard worker"]
            resume_data["skills"] = [
                skill for skill in skills 
                if skill.lower() not in [b.lower() for b in buzzword_skills]
            ]
    
    return resume_data

def add_quantification_to_bullets(resume_data):
    """
    Add quantification to bullet points that lack numbers/metrics
    This is a helper - the main quantification should come from the AI prompt
    """
    if "experience" not in resume_data or not isinstance(resume_data["experience"], list):
        return resume_data
    
    # Common quantification patterns to check for
    quantification_patterns = [
        r'\d+%',  # percentages
        r'\d+\+',  # numbers with +
        r'\$\d+',  # dollar amounts
        r'\d+[KM]',  # thousands/millions
        r'\d+\s*(seconds?|minutes?|hours?|days?|months?|years?)',  # time periods
        r'\d+\s*(users?|requests?|features?|projects?|developers?|team members?)',  # counts
    ]
    
    import re
    
    for exp in resume_data["experience"]:
        if "highlights" in exp and isinstance(exp["highlights"], list):
            for i, highlight in enumerate(exp["highlights"]):
                if isinstance(highlight, str):
                    # Check if already quantified
                    has_quantification = any(re.search(pattern, highlight, re.IGNORECASE) for pattern in quantification_patterns)
                    
                    # If no quantification and highlight is substantial, add a note in comment
                    # (We can't auto-add numbers, but we can ensure the prompt handles it)
                    if not has_quantification and len(highlight.split()) > 5:
                        # The AI should have added quantification, but if it didn't, 
                        # we'll leave it as-is since we can't fabricate numbers
                        pass
    
    return resume_data

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

def enforce_career_progression(resume_data, job_domain=""):
    """
    Ensure job titles show logical career progression based on job description domain:
    - First (most recent) = Senior/Lead level
    - Middle = Mid-level (no Senior prefix)
    - Last (oldest) = Entry level (Junior or no prefix)
    """
    if "experience" not in resume_data or not isinstance(resume_data["experience"], list):
        return resume_data
    
    experiences = resume_data["experience"]
    if len(experiences) < 1:
        return resume_data
    
    num_experiences = len(experiences)
    
    # Use provided domain or extract from first experience
    domain = job_domain
    if not domain:
        first_title = experiences[0].get("title", "")
        # Extract domain by removing level prefixes
        title_clean = first_title
        for prefix in ["Senior", "Lead", "Principal", "Staff", "Junior", "Mid-level", "Mid"]:
            title_clean = title_clean.replace(prefix, "").strip()
        domain = title_clean if title_clean else "Developer"
    
    # Determine base title format
    if "Developer" in domain or "Engineer" in domain:
        base_title = domain
    else:
        base_title = f"{domain} Developer"
    
    # First (most recent) - should be Senior/Lead
    first_title = experiences[0].get("title", "")
    if not any(word.lower() in first_title.lower() for word in ["Senior", "Lead", "Principal", "Staff"]):
        experiences[0]["title"] = f"Senior {base_title}"
    else:
        # Ensure domain is correct even if Senior is present
        if domain.lower() not in first_title.lower():
            # Replace with correct domain
            for prefix in ["Senior", "Lead", "Principal", "Staff"]:
                if prefix.lower() in first_title.lower():
                    experiences[0]["title"] = f"{prefix} {base_title}"
                    break
    
    # Last (oldest) - MUST be entry level (cannot be Senior or Mid)
    if num_experiences >= 2:
        last_title = experiences[-1].get("title", "")
        # Remove any senior/mid level prefixes
        last_title_clean = last_title
        for prefix in ["Senior", "Lead", "Principal", "Staff", "Mid-level", "Mid"]:
            if prefix.lower() in last_title_clean.lower():
                last_title_clean = last_title_clean.replace(prefix, "").strip()
                break
        
        # Ensure it's entry level - add "Junior" if it looks too advanced, or use base title
        if any(word.lower() in last_title_clean.lower() for word in ["Senior", "Lead", "Principal", "Staff"]):
            # Force entry level
            experiences[-1]["title"] = f"Junior {base_title}" if num_experiences > 1 else base_title
        elif domain.lower() not in last_title_clean.lower():
            # Use base title or junior version for first job
            experiences[-1]["title"] = f"Junior {base_title}" if num_experiences > 2 else base_title
        else:
            # Keep the cleaned title but ensure it's not senior
            experiences[-1]["title"] = last_title_clean
    
    # Middle experiences - should be mid-level (no Senior, no Junior)
    for i in range(1, num_experiences - 1):
        mid_title = experiences[i].get("title", "")
        # Remove Senior/Lead/Junior if present
        mid_title_clean = mid_title
        for prefix in ["Senior", "Lead", "Principal", "Staff", "Junior", "Mid-level", "Mid"]:
            if prefix.lower() in mid_title_clean.lower():
                mid_title_clean = mid_title_clean.replace(prefix, "").strip()
                break
        
        # Ensure domain is correct and it's mid-level (no prefix)
        if domain.lower() not in mid_title_clean.lower():
            experiences[i]["title"] = base_title
        else:
            experiences[i]["title"] = mid_title_clean
    
    return resume_data

def extract_skills_for_ats(job_description: str, model) -> dict:
    """
    Extract hard skills and soft skills from job description for ATS optimization
    Returns dict with hard_skills, soft_skills, and keywords
    """
    extract_prompt = f"""
    Analyze the following job description and extract ALL skills and keywords for ATS (Applicant Tracking System) matching.
    
    JOB DESCRIPTION:
    {job_description}
    
    Identify and return a JSON object with:
    1. hard_skills: A comprehensive list of ALL technical skills, technologies, tools, frameworks, languages, platforms mentioned (e.g., ["React", "TypeScript", "Node.js", "AWS", "Docker", "GraphQL", "REST API", "PostgreSQL", "MongoDB", "Jest", "Cypress", "Git", "CI/CD", "Agile", "Scrum"])
    2. soft_skills: A list of soft skills, personal attributes, and behavioral competencies mentioned (e.g., ["Communication", "Teamwork", "Leadership", "Problem-solving", "Collaboration", "Time management"])
    3. keywords: A list of important keywords, phrases, and terms that should appear in the resume (include technical terms, methodologies, industry terms)
    4. required_technologies: Specific technologies that are explicitly required (prioritize these)
    5. preferred_technologies: Technologies mentioned as "nice to have" or "preferred"
    
    IMPORTANT:
    - Extract EVERY technical skill mentioned, even if it's just mentioned once
    - Include variations (e.g., "React" and "React.js" if both appear)
    - Include methodologies (e.g., "Agile", "Scrum", "DevOps", "CI/CD")
    - Include tools and platforms (e.g., "AWS", "Docker", "Kubernetes", "GitHub")
    - Be comprehensive - ATS systems match on exact keywords
    
    Return ONLY a valid JSON object, no additional text.
    """
    
    try:
        response = model.generate_content(extract_prompt)
        text = response.text.strip()
        # Clean up JSON if wrapped in markdown
        if '```json' in text:
            json_str = text.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '```' in text:
            json_str = text.split('```', 1)[1].split('```', 1)[0].strip()
        else:
            json_str = text
        
        result = json.loads(json_str)
        # Ensure all fields exist
        return {
            "hard_skills": result.get("hard_skills", []),
            "soft_skills": result.get("soft_skills", []),
            "keywords": result.get("keywords", []),
            "required_technologies": result.get("required_technologies", []),
            "preferred_technologies": result.get("preferred_technologies", [])
        }
    except Exception as e:
        print(f"Error extracting skills: {e}")
        return {
            "hard_skills": [],
            "soft_skills": [],
            "keywords": [],
            "required_technologies": [],
            "preferred_technologies": []
        }

def extract_education_requirements(job_description: str, model) -> dict:
    """
    Extract education requirements from job description
    Returns dict with education_level, degree_type, and any specific requirements
    """
    extract_prompt = f"""
    Analyze the following job description and extract education requirements.
    
    JOB DESCRIPTION:
    {job_description}
    
    Identify and return a JSON object with:
    1. education_level: The required education level (e.g., "Bachelor's degree", "Master's degree", "Advanced degree", "PhD", "High school", "Associate's degree", or "Not specified")
    2. degree_type: The type of degree if specified (e.g., "Computer Science", "Engineering", "Business", etc.) or "Any" if not specified
    3. is_required: true if education is required, false if preferred or not mentioned
    4. notes: Any additional education-related notes or requirements
    
    Return ONLY a valid JSON object, no additional text.
    """
    
    try:
        response = model.generate_content(extract_prompt)
        text = response.text.strip()
        # Clean up JSON if wrapped in markdown
        if '```json' in text:
            json_str = text.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '```' in text:
            json_str = text.split('```', 1)[1].split('```', 1)[0].strip()
        else:
            json_str = text
        
        result = json.loads(json_str)
        return result
    except Exception as e:
        print(f"Error extracting education requirements: {e}")
        return {
            "education_level": "Not specified",
            "degree_type": "Any",
            "is_required": False,
            "notes": ""
        }

def extract_address_requirements(job_description: str) -> dict:
    """
    Extract address/location requirements from job description
    """
    job_lower = job_description.lower()
    
    requirements = {
        "requires_address": False,
        "location_preference": None,
        "remote_allowed": False,
        "relocation_required": False
    }
    
    # Check for remote work mentions
    if any(term in job_lower for term in ["remote", "work from home", "wfh", "distributed team"]):
        requirements["remote_allowed"] = True
    
    # Check for location-specific requirements
    if any(term in job_lower for term in ["must be located in", "based in", "relocate to", "onsite", "on-site"]):
        requirements["requires_address"] = True
    
    # Check for relocation mentions
    if any(term in job_lower for term in ["relocation", "relocate", "willing to relocate"]):
        requirements["relocation_required"] = True
    
    return requirements

def validate_address(contact: dict) -> tuple[bool, str]:
    """
    Validate if address is complete in contact information
    Returns (is_valid, error_message)
    """
    location = contact.get("location", "")
    
    if not location or not location.strip():
        return False, "Address is missing"
    
    location_parts = location.split(",")
    # A complete address should have at least city and country/state
    if len(location_parts) < 2:
        return False, "Address is incomplete - should include city and country/state"
    
    # Check if it's too short (likely incomplete)
    if len(location.strip()) < 5:
        return False, "Address appears to be incomplete"
    
    return True, ""

def extract_job_title(job_description: str, model) -> str:
    """
    Extract the job title from the job description using AI
    """
    extract_prompt = f"""
    Extract the job title from the following job description. Return ONLY the job title, nothing else.
    
    JOB DESCRIPTION:
    {job_description}
    
    Return the exact job title (e.g., "Full-stack Engineer", "Senior Software Developer", "Product Manager").
    """
    
    try:
        response = model.generate_content(extract_prompt)
        job_title = response.text.strip()
        # Clean up if wrapped in quotes or markdown
        job_title = job_title.strip('"\'`')
        if job_title.startswith('```'):
            job_title = job_title.split('```')[1].strip()
        return job_title
    except Exception as e:
        print(f"Error extracting job title: {e}")
        return ""

def job_title_in_resume(job_title: str, resume_data: dict) -> bool:
    """
    Check if the job title exists anywhere in the resume (in experience titles or summary)
    """
    if not job_title:
        return False
    
    job_title_lower = job_title.lower()
    
    # Check in summary
    summary = resume_data.get("summary", "").lower()
    if job_title_lower in summary:
        return True
    
    # Check in experience titles
    experiences = resume_data.get("experience", [])
    for exp in experiences:
        title = exp.get("title", "").lower()
        # Check if job title is contained in experience title or vice versa
        if job_title_lower in title or title in job_title_lower:
            return True
        # Also check individual words for partial matches
        job_title_words = set(job_title_lower.split())
        title_words = set(title.split())
        # If more than 50% of words match, consider it found
        if len(job_title_words.intersection(title_words)) / max(len(job_title_words), 1) > 0.5:
            return True
    
    return False

def generate_headline(job_title: str, resume_data: dict, model) -> str:
    """
    Generate a professional headline based on the job title and resume
    """
    if not job_title:
        return ""
    
    name = resume_data.get("name", "")
    summary = resume_data.get("summary", "")
    
    # Extract years of experience from summary if available
    years_match = re.search(r'(\d+)\+?\s*years?', summary, re.IGNORECASE)
    years_exp = years_match.group(1) if years_match else ""
    
    # Extract key technologies from summary (first few mentioned)
    tech_keywords = []
    common_tech = ['React', 'Python', 'JavaScript', 'Node.js', 'AWS', 'Shopify', 'TypeScript', 'Next.js', 'Docker', 'Kubernetes']
    for tech in common_tech:
        if tech.lower() in summary.lower():
            tech_keywords.append(tech)
            if len(tech_keywords) >= 3:
                break
    
    headline_prompt = f"""
    Create a professional headline for a resume based on the following information:
    
    JOB TITLE: {job_title}
    CANDIDATE NAME: {name}
    CURRENT SUMMARY: {summary}
    
    The headline should:
    1. Include the exact job title "{job_title}" prominently at the beginning
    2. Be concise (one line, maximum 80 characters)
    3. Be professional and compelling
    4. Position the candidate as qualified for this role
    5. Use the format: "[Job Title] | [Key Qualification/Experience]" or similar
    6. If years of experience are mentioned ({years_exp} years), include them naturally
    
    Examples:
    - "Full-stack Engineer | 6+ Years Building Scalable Web Applications"
    - "Senior Software Developer | Expert in React, Node.js, and Cloud Architecture"
    - "Product Manager | Driving Product Strategy & Cross-functional Leadership"
    
    Return ONLY the headline text, nothing else. Do not include quotes or markdown formatting.
    """
    
    try:
        response = model.generate_content(headline_prompt)
        headline = response.text.strip()
        # Clean up if wrapped in quotes or markdown
        headline = headline.strip('"\'`')
        if '```' in headline:
            # Extract from markdown code blocks
            parts = headline.split('```')
            if len(parts) > 1:
                headline = parts[-1].strip()
        # Remove any leading/trailing punctuation that might have been added
        headline = headline.strip('.,;:')
        
        # Validate headline contains the job title
        if job_title.lower() not in headline.lower():
            # If AI didn't include job title, prepend it
            headline = f"{job_title} | {headline}"
        
        return headline
    except Exception as e:
        print(f"Error generating headline: {e}")
        # Fallback to simple headline with job title
        if years_exp:
            return f"{job_title} | {years_exp}+ Years of Experience"
        else:
            return job_title

def tailor_resume(job_description, model, template = "resume_templates/michael.json"):
    """
    Tailor the resume based on the job description
    Uses the template resume JSON and creates a tailored version
    """
    # Load the template resume
    template_path = os.path.join(os.path.dirname(__file__), template)
    with open(template_path, "r") as f:
        resume_structure = json.load(f)
    
    # Extract job title from job description
    job_title = extract_job_title(job_description, model)
    
    # Extract domain from job title (e.g., "Full Stack", "Shopify", "iOS", "Frontend")
    domain = ""
    if job_title:
        job_title_lower = job_title.lower()
        # Extract domain keywords
        domain_keywords = {
            "full stack": "Full Stack",
            "full-stack": "Full Stack",
            "shopify": "Shopify",
            "ios": "iOS",
            "android": "Android",
            "react": "React",
            "angular": "Angular",
            "vue": "Vue",
            "node": "Node.js",
            "python": "Python",
            "java": "Java",
            "frontend": "Frontend",
            "front-end": "Frontend",
            "backend": "Backend",
            "back-end": "Backend",
            "devops": "DevOps",
            "cloud": "Cloud",
            "mobile": "Mobile"
        }
        for keyword, domain_name in domain_keywords.items():
            if keyword in job_title_lower:
                domain = domain_name
                break
        
        # If no specific domain found, try to extract from job title structure
        if not domain:
            # Remove common level prefixes
            title_clean = job_title
            for prefix in ["Senior", "Lead", "Principal", "Staff", "Junior", "Mid-level", "Mid"]:
                title_clean = title_clean.replace(prefix, "").strip()
            # Use the remaining as domain
            if title_clean:
                domain = title_clean
    
    # Check if job title exists in resume
    title_found = job_title_in_resume(job_title, resume_structure) if job_title else False
    
    # Always generate headline based on job description to ensure it's included
    # This helps with ATS (Applicant Tracking Systems) and recruiter searches
    headline = ""
    if job_title:
        headline = generate_headline(job_title, resume_structure, model)
        # If title not found, we'll also mention it in the prompt to add it to summary
    
    # Extract skills for ATS optimization (critical for Jobscan match rate)
    skills_analysis = extract_skills_for_ats(job_description, model)
    hard_skills = skills_analysis.get("hard_skills", [])
    soft_skills = skills_analysis.get("soft_skills", [])
    keywords = skills_analysis.get("keywords", [])
    required_tech = skills_analysis.get("required_technologies", [])
    
    # Extract education requirements from job description
    education_requirements = extract_education_requirements(job_description, model)
    
    # Extract address requirements
    address_requirements = extract_address_requirements(job_description)
    
    # Validate current address
    contact = resume_structure.get("contact", {})
    address_valid, address_error = validate_address(contact)
    
    # Check education match
    current_education = resume_structure.get("education", {})
    current_degree = current_education.get("degree", "") if isinstance(current_education, dict) else ""
    education_mismatch = False
    education_note = ""
    
    if education_requirements.get("education_level") and education_requirements["education_level"] != "Not specified":
        required_level = education_requirements["education_level"].lower()
        current_degree_lower = current_degree.lower()
        
        # Check for mismatches
        if "advanced degree" in required_level or "master" in required_level or "phd" in required_level or "doctorate" in required_level:
            if "bachelor" in current_degree_lower and "master" not in current_degree_lower and "phd" not in current_degree_lower and "doctorate" not in current_degree_lower:
                education_mismatch = True
                education_note = f"The job requires {education_requirements['education_level']}, but the resume shows {current_degree}. If experience is strong, this should be addressed in the summary."
    
    # Create the tailoring prompt
    tailoring_prompt = f"""
    I need to tailor my resume for a specific job. I'll provide my current resume structure in JSON format and the job description.
    
    JOB DESCRIPTION:
    {job_description}
    
    MY CURRENT RESUME (in JSON format):
    {json.dumps(resume_structure, indent=2)}
    
    CRITICAL REQUIREMENTS TO ADDRESS:
    
    A. ADDRESS/LOCATION VALIDATION:
       - Current address status: {"✓ Complete" if address_valid else f"✗ {address_error}"}
       - Current location in resume: "{contact.get('location', 'MISSING')}"
       - REQUIRED: Ensure the "location" field in contact contains a COMPLETE address
       - Format should be: "City, State/Province, Country" (e.g., "Bandung, West Java, Indonesia")
       - If address is missing or incomplete, use the existing location but make it more complete
       - Recruiters use addresses to validate location for job matches - this is critical for ATS systems
    
    B. EDUCATION REQUIREMENTS MATCH:
       - Job requires: {education_requirements.get('education_level', 'Not specified')}
       - Current education: {current_degree if current_degree else 'Not specified'}
       - Education match status: {"✓ Matches" if not education_mismatch else f"✗ MISMATCH - {education_note}"}
       - If there's a mismatch (e.g., job requires Advanced degree but resume shows Bachelor's):
         * Keep the actual education degree as-is (do not falsify)
         * BUT add a note in the SUMMARY section explaining how strong experience compensates
         * Example: "While the position may prefer an advanced degree, my X+ years of hands-on experience in [relevant areas] demonstrate equivalent expertise..."
         * This addresses the mismatch professionally without misrepresenting qualifications
    
    C. CRITICAL ATS OPTIMIZATION - SKILLS MATCHING (This directly affects Jobscan match rate):
       - HARD SKILLS REQUIRED: {len(hard_skills)} skills found in job description
       - Required hard skills: {', '.join(hard_skills[:15])}{'...' if len(hard_skills) > 15 else ''}
       - SOFT SKILLS REQUIRED: {len(soft_skills)} skills found
       - Required soft skills: {', '.join(soft_skills) if soft_skills else 'None specified'}
       - KEYWORDS TO INCLUDE: {len(keywords)} important keywords
       - CRITICAL: ALL of these skills MUST appear in the resume in multiple places:
         * Summary section: Include as many hard skills as possible (use <strong> tags)
         * Skills section: List ALL hard skills from job description, prioritize required ones
         * Experience highlights: Incorporate hard skills naturally in bullet points
         * Use EXACT terminology from job description (e.g., if job says "React", use "React" not "React.js")
       - For soft skills: Integrate naturally into summary and experience descriptions
       - ATS systems match on exact keywords - missing skills = lower match rate
    
    Based on the job description, please create a tailored version of my resume by modifying the following sections:
    
    0. Headline (NEW FIELD - REQUIRED - add this to the JSON):
       - The job title from the job description is: "{job_title}"
       - ALWAYS create a "headline" field with a professional headline that includes the exact job title
       - The headline should be: "{headline}" (use this exact headline)
       - The headline format should be: "[Job Title] | [Key Qualification/Experience]"
       - This headline is critical for ATS (Applicant Tracking Systems) to find the resume when recruiters search by job title
       - Even if the job title appears elsewhere in the resume, include this headline field
    
    1. Summary: Rewrite to emphasize skills and experiences relevant to this specific job
       - Use <strong>bold</strong> formatting for ALL technical skills from the job description
       - MUST INCLUDE as many hard skills as possible: {', '.join(hard_skills[:10])}{'...' if len(hard_skills) > 10 else ''}
       - Make the summary concise but comprehensive - aim for 3-4 sentences that pack in keywords
       - If the job title "{job_title}" is not in my resume, consider mentioning it in the summary as well
       - Integrate soft skills naturally: {', '.join(soft_skills) if soft_skills else 'None'}
       - {"CRITICAL - EDUCATION MISMATCH: The job requires {education_requirements.get('education_level', 'Advanced degree')} but my resume shows {current_degree}. REQUIRED: Add a professional note at the END of the summary (as the final 1-2 sentences) explaining how strong experience compensates. Calculate years from experience section and use that number. Example: 'While the position may prefer an advanced degree, my 7+ years of hands-on experience in [relevant technologies from job description] demonstrate equivalent expertise and practical knowledge that aligns with the role requirements.' Make it specific to the job - mention relevant technologies/skills from the job description." if education_mismatch else ""}
       - ATS OPTIMIZATION: The summary is scanned first - include maximum keywords here
       - AVOID REPETITION: Don't repeat the same phrases or words multiple times in the summary
       - AVOID BUZZWORDS: DO NOT use vague buzzwords like "self-starter", "attention to detail", "problem-solving", "proven track record", "team player", "hard worker", "go-getter", "think outside the box", "synergy", "leverage", "action-oriented", "detail-oriented", "passionate", "rockstar", "ninja", "guru"
       - Instead of buzzwords, use specific, concrete language that shows actual skills and achievements
       - Example: Instead of "self-starter with attention to detail", use "independently delivered [specific achievement] with meticulous code review processes"
    
    2. Experience: For each experience entry (CRITICAL - CREATE TITLES BASED ON JOB DESCRIPTION):
       - Keep the company name and period the same
       - DO NOT use the template job titles - CREATE NEW TITLES based on the job description domain
       - The job title from the job description is: "{job_title}"
       - The domain to use is: "{domain}" (extract from job title)
       - CRITICAL CAREER PROGRESSION RULES (based on chronological order - oldest to newest):
         * The LAST job in the list (OLDEST/FIRST job chronologically) MUST be ENTRY LEVEL:
           - Use: "Junior [Domain] Developer", "[Domain] Developer", or "Web Developer" (for first job)
           - Examples: "Junior Full Stack Developer", "Web Developer", "Frontend Developer"
           - This is the STARTING point of the career - cannot be Senior or Mid-level
         
         * The MIDDLE job(s) should be MID-LEVEL (no "Senior" prefix):
           - Use: "[Domain] Developer", "[Domain] Engineer", or "[Domain] Software Engineer"
           - Examples: "Full Stack Developer", "Shopify Developer", "Frontend Engineer"
           - Show progression from entry level
         
         * The FIRST job in the list (MOST RECENT/NEWEST) should be SENIOR/LEAD level:
           - Use: "Senior [Domain] Developer", "Lead [Domain] Developer", or "Senior [Domain] Engineer"
           - Examples: "Senior Full Stack Developer", "Lead Full Stack Engineer"
           - This shows career growth to senior level
       
       - STEP-BY-STEP PROGRESSION EXAMPLES:
         * For "Full Stack Engineer" job:
           - Oldest (last): "Junior Full Stack Developer" or "Web Developer"
           - Middle: "Full Stack Developer"
           - Newest (first): "Senior Full Stack Developer"
         
         * For "Shopify Developer" job:
           - Oldest (last): "Web Developer" or "Junior Frontend Developer"
           - Middle: "Shopify Developer" or "Frontend Developer"
           - Newest (first): "Senior Shopify Developer"
       
       - IMPORTANT: The progression must show GROWTH from entry → mid → senior
       - DO NOT start with Senior or Mid-level titles for the oldest job
       - All titles should match the job description's domain/technology
       - Tailor the summary to match the job description, to highlight relevant achievements, using markdown for technical terms
       - The 'highlights' section is CRITICAL for ATS matching and impact
       - CRITICAL RULES FOR HIGHLIGHTS:
         * AVOID REPETITIVE ACTION VERBS: Never use the same action verb more than 2 times across the entire resume
         * AVOID DUPLICATE WORDS IN SAME SENTENCE: Never repeat the same word twice in one bullet (e.g., "Architected and architected" is WRONG - use "Architected and engineered" instead)
         * Use varied action verbs: Instead of "Developed" 3 times, use: "Architected", "Built", "Engineered", "Designed", "Implemented", "Created", "Delivered", "Launched", "Spearheaded", "Led", "Optimized", "Enhanced", "Streamlined", "Transformed", "Established", "Pioneered"
         * QUANTIFY EVERYTHING: Every single highlight MUST include specific numbers, metrics, or percentages - NO EXCEPTIONS
           - Examples: "Increased performance by 40%", "Reduced load time by 2.5 seconds", "Managed team of 5 developers", "Handled 1M+ daily requests", "Improved conversion rate by 15%", "Deployed 50+ features", "Reduced costs by $200K annually", "Improved user engagement by 30%", "Reduced security incidents by 40%", "Increased deployment efficiency by 50%"
           - If you cannot find exact numbers, use reasonable estimates based on context (e.g., "Managed team of 5+ developers", "Handled 100K+ daily requests", "Improved performance by 25-30%")
           - DO NOT create highlights without numbers - every bullet point must have quantification
         * Show IMPACT not just responsibilities: Focus on results and outcomes
         * Make each bullet point unique: Avoid similar phrasing or repetitive patterns
         * Start with strong action verbs: Use powerful verbs that show leadership and impact
       - For each highlight, incorporate 2-3 hard skills from the job description naturally
       - Use <strong>bold</strong> tags for technical terms (e.g., "Built <strong>React</strong> applications using <strong>TypeScript</strong> and <strong>GraphQL</strong>")
       - Re-write and tailor each highlight to include job description keywords
       - Ensure required technologies appear in experience: {', '.join(required_tech[:8]) if required_tech else 'All hard skills'}
       - Adjust the skills array in each experience to include relevant hard skills from job description
       - Each experience entry should have 4-6 strong, quantified highlights
    
    3. Skills: CRITICAL - This section directly affects ATS match rate
       - MUST INCLUDE ALL hard skills from job description: {len(hard_skills)} skills total
       - Required hard skills to include: {', '.join(hard_skills[:20])}{'...' if len(hard_skills) > 20 else ''}
       - Prioritize required technologies: {', '.join(required_tech) if required_tech else 'All hard skills'}
       - Organize skills into logical categories (e.g., "Frontend", "Backend", "Tools", "Methodologies")
       - Use EXACT terminology from job description (if job says "React", use "React" not "React.js")
       - Keep relevant existing skills that match job requirements
       - Remove or de-prioritize skills not mentioned in job description
       - If a skill category exists, add missing hard skills to appropriate categories
       - AVOID BUZZWORDS IN SKILLS: Do NOT include vague buzzwords like "Self-starter", "Attention to detail", "Problem-solving", "Team player", "Hard worker" in the skills section
       - If you have a "Soft Skills" category, use specific, measurable soft skills like "Communication", "Collaboration", "Leadership", "Agile Methodology" - avoid clichés
       - ATS systems scan this section - completeness is critical for match rate
    
    Do NOT modify:
    - Name
    - Company names and dates
    - Education factual information (degree name, university name, period) - keep these factual
    
    MUST MODIFY:
    4. Education: CRITICAL - Tailor the education section description based on job description
       - Keep factual information unchanged: degree name, university name, and period (dates) - DO NOT modify these
       - Job education requirements: {education_requirements.get('education_level', 'Not specified')}
       - Degree type preferred: {education_requirements.get('degree_type', 'Any')}
       - Current education: {current_degree if current_degree else 'Not specified'}
       - REQUIRED: Create or modify the "description" field in the education section to match the job description
       - The description should highlight:
         * Relevant coursework that matches job requirements (e.g., if job mentions AI/ML, highlight AI/ML courses; if job mentions databases, highlight database courses)
         * Concentrations or specializations that align with the job (e.g., "Software Development", "Algorithm Design", "Database Management Systems")
         * Academic achievements, projects, or research relevant to the role
         * Technical skills or knowledge gained that match job requirements from the job description
       - Analyze the job description for specific technologies, methodologies, or domains mentioned
       - If the job description mentions specific technologies (e.g., React, Python, AWS, AI), include relevant coursework or projects using those technologies
       - If the job description emphasizes certain skills (e.g., full-stack development, cloud computing, machine learning), highlight related academic work
       - Make the description concise but impactful (2-3 sentences, approximately 50-100 words)
       - Use <strong>bold</strong> tags for technical terms, technologies, and relevant skills mentioned in the job description
       - If the degree type matches job requirements, emphasize that alignment
       - If there's a mismatch, focus on relevant coursework/experience that shows equivalent knowledge
       - Example for Full Stack Engineer role: "Major concentration in <strong>Software Development</strong>, <strong>Algorithm Design</strong>, and <strong>Database Management Systems</strong>. Completed coursework in web development, distributed systems, and software engineering principles. Academic projects focused on building scalable web applications using modern frameworks."
       - Example for AI/ML role: "Specialized in <strong>Machine Learning</strong> and <strong>Data Science</strong> with coursework in neural networks, natural language processing, and computer vision. Completed capstone project on AI-powered recommendation systems."
       - IMPORTANT: The description must be DIFFERENT for each job application - it should reflect the specific job description requirements
    
    MUST MODIFY:
    - Contact location: {"Ensure location is complete (City, State/Province, Country format)" if not address_valid else "Keep location as-is"}
    - Summary: {"Add note about experience compensating for education if needed" if education_mismatch else "Standard tailoring"}
    
    CRITICAL FORMATTING RULES:
    - Use ONLY HTML <strong>bold</strong> tags for all technical terms and skills (like <strong>JavaScript</strong>, <strong>Python</strong>, <strong>AWS</strong>, etc)
    - DO NOT use markdown **bold** syntax (no asterisks)
    - DO NOT use double asterisks (**) anywhere in the text
    - All bold text must use <strong>text</strong> HTML format only
    
    CRITICAL QUALITY RULES (Based on Resume Worded analysis - Score 58 → Target 80+):
    1. AVOID REPETITIVE ACTION VERBS:
       - Never use the same action verb more than 2 times across the entire resume
       - Use varied, powerful action verbs: Architected, Built, Engineered, Designed, Implemented, Created, Delivered, Launched, Spearheaded, Led, Optimized, Enhanced, Streamlined, Transformed, Established, Pioneered, Accelerated, Automated, Refactored, Migrated, Scaled, Deployed, Integrated, Orchestrated
       - Track verb usage: If you've used "Developed" twice, use "Architected" or "Engineered" for the third similar action
       - If you've used "Optimized" twice, use "Enhanced", "Streamlined", or "Improved" instead
       - Common overused verbs to avoid repeating: Developed, Optimized, Created, Implemented, Built
    
    2. QUANTIFY EVERY BULLET POINT (CRITICAL - NO EXCEPTIONS):
       - Every single highlight/bullet point MUST include specific numbers, metrics, percentages, or quantifiable results
       - If a bullet point doesn't have a number, it is INCOMPLETE and must be rewritten
       - Examples of good quantification:
         * "Increased application performance by 40% through optimization"
         * "Reduced API response time from 500ms to 150ms"
         * "Managed team of 5 developers across 3 projects"
         * "Handled 1M+ daily API requests with 99.9% uptime"
         * "Improved conversion rate by 15% through A/B testing"
         * "Deployed 50+ features in 6 months"
         * "Reduced infrastructure costs by $200K annually"
         * "Increased user engagement by 30%"
         * "Reduced bug reports by 25% through improved testing"
         * "Improved page load time by 2.5 seconds"
       - If exact numbers aren't available, use reasonable estimates based on context
       - Quantification shows impact and makes achievements stand out
       - Target: 15+ quantified bullets for a strong resume
    
    3. AVOID REPETITIVE PHRASES:
       - Don't repeat the same phrases or sentence structures
       - Vary your language and sentence construction
       - Each bullet point should be unique in structure and content
       - Avoid starting multiple bullets with the same phrase pattern
    
    4. STRENGTHEN WEAK ROLES:
       - Every role should tell a strong story about accomplishments
       - Focus on impact and results, not just responsibilities
       - Use powerful action verbs at the start of each bullet
       - Show progression and growth in responsibilities
       - Make each role description compelling and unique
       - Each role should have 4-6 strong, quantified bullet points
    
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
        
        # Always add headline if it was generated (ensures it's included even if AI didn't add it)
        if headline:
            tailored_resume["headline"] = headline
        
        # Fix address if incomplete (critical for ATS systems)
        if "contact" in tailored_resume:
            current_location = tailored_resume["contact"].get("location", "")
            location_valid, _ = validate_address(tailored_resume["contact"])
            
            if not location_valid:
                # Try to enhance the location
                if current_location:
                    # If location exists but is incomplete, try to complete it
                    location_parts = current_location.split(",")
                    if len(location_parts) == 1:
                        # Only city provided, add country (default to Indonesia based on common templates)
                        tailored_resume["contact"]["location"] = f"{current_location}, Indonesia"
                    elif len(location_parts) == 2:
                        # City and state, but might need country
                        if "Indonesia" not in current_location and "USA" not in current_location and "United States" not in current_location:
                            # Add country if not present
                            tailored_resume["contact"]["location"] = f"{current_location}, Indonesia"
                else:
                    # Location is completely missing - use a placeholder that should be updated
                    tailored_resume["contact"]["location"] = "City, State/Province, Country"
        
        # Enforce career progression in job titles based on job description domain
        tailored_resume = enforce_career_progression(tailored_resume, domain)
        
        # ATS Optimization: Ensure all required hard skills are included
        if hard_skills:
            # Add missing hard skills to skills section
            if "skills" in tailored_resume:
                skills = tailored_resume["skills"]
                
                # If skills is a dict (categorized), add missing skills to appropriate categories
                if isinstance(skills, dict):
                    # Create a flat list of existing skills for checking
                    existing_skills_flat = []
                    for category, skill_list in skills.items():
                        if isinstance(skill_list, list):
                            existing_skills_flat.extend([s.lower() for s in skill_list])
                    
                    # Find missing skills
                    missing_skills = []
                    for skill in hard_skills:
                        skill_lower = skill.lower()
                        # Check if skill or variation exists
                        found = False
                        for existing in existing_skills_flat:
                            if skill_lower in existing or existing in skill_lower:
                                found = True
                                break
                        if not found:
                            missing_skills.append(skill)
                    
                    # Add missing skills to appropriate category or create "Technologies" category
                    if missing_skills:
                        if "Technologies" in skills:
                            # Add to existing Technologies category
                            existing_tech = skills["Technologies"]
                            if isinstance(existing_tech, list):
                                skills["Technologies"] = list(set(existing_tech + missing_skills))
                        else:
                            # Create Technologies category
                            skills["Technologies"] = missing_skills
                
                # If skills is a list, add missing skills
                elif isinstance(skills, list):
                    existing_skills_lower = [s.lower() for s in skills]
                    for skill in hard_skills:
                        if skill.lower() not in existing_skills_lower:
                            # Check for variations
                            found_variation = False
                            for existing in existing_skills_lower:
                                if skill.lower() in existing or existing in skill.lower():
                                    found_variation = True
                                    break
                            if not found_variation:
                                skills.append(skill)
        
        # Post-process to fix repetitive verbs, remove buzzwords, and add quantification
        tailored_resume = fix_repetitive_verbs(tailored_resume)
        tailored_resume = remove_buzzwords(tailored_resume)
        tailored_resume = add_quantification_to_bullets(tailored_resume)
        
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
    
    # Generate contact links HTML - only use href for LinkedIn, others display as text
    contact_links = []
    location_text = ""
    
    for key, value in contact.items():
        if key == "location":  # Handle location separately for right side
            if value:
                location_text = value
        else:
            # Extract display text: for mailto: extract email, for tel: extract phone, otherwise use full URL
            if value.startswith("mailto:"):
                display_text = value.replace("mailto:", "")
            elif value.startswith("tel:"):
                display_text = value.replace("tel:", "")
            else:
                display_text = value
            
            # Only use href for LinkedIn links
            if key.lower() == "linkedin" or "linkedin.com" in value.lower():
                # Ensure LinkedIn URL has proper protocol
                linkedin_url = value
                if not linkedin_url.startswith("http://") and not linkedin_url.startswith("https://"):
                    if linkedin_url.startswith("www."):
                        linkedin_url = "https://" + linkedin_url
                    else:
                        linkedin_url = "https://www." + linkedin_url
                contact_links.append(f'<a href="{linkedin_url}" style="margin: 0 0.5em; color: #333333; text-decoration: none;">{display_text}</a>')
            else:
                # For other contacts (email, phone, etc.), display as plain text without href
                contact_links.append(f'<span style="margin: 0 0.5em; color: #333333;">{display_text}</span>')
    
    # Combine contacts and location in a flex container
    contacts_text = " • ".join(contact_links)
    contacts_html = f'<div style="display: flex; flex-direction: row; justify-content: space-between; width:100%"><p >{contacts_text}</p><p>{location_text}</p></div>'
    
    top_section = top_section_template
    top_section = top_section.replace("{{name}}", name)
    
    # Add headline if it exists
    headline = tailored_resume.get("headline", "")
    headline_section = ""
    if headline:
        headline_section = f'<div style="color: #666666; font-size: 1.1em; margin-bottom: 0.5em; font-weight: 500; text-align: left;">{headline}</div>'
    top_section = top_section.replace("{{headline}}", headline_section)
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
    
    # Generate Skills Section
    skills = tailored_resume["skills"]
    skills_html = ""
    if isinstance(skills, dict):
        for category, skill_list in skills.items():
            if isinstance(skill_list, list):
                skills_text = ", ".join(skill_list)
            else:
                skills_text = str(skill_list)
            
            skill_item = skill_section_item_template
            skill_item = skill_item.replace("{{category}}", category)
            skill_item = skill_item.replace("{{skills}}", skills_text)
            skills_html += skill_item + "\n"
    
    skills_section = skills_section_template.replace("{{skills}}", skills_html)
    
    # Generate Education Section (now tailored based on job description)
    education_section = education_section_template
    if isinstance(tailored_resume["education"], dict):
        education = tailored_resume["education"]
        degree = education.get("degree", "")
        university = education.get("university", "")
        period = education.get("period", "")
        # Description should be tailored by AI based on job description
        description = education.get("description", "")
        
        # If no description was created by AI, create a basic one (but ideally AI should have created it based on job description)
        if not description or description.strip() == "":
            description = f"Relevant coursework and projects in software development and computer science."
        
        # Replace education information with actual values from tailored resume
        education_section = education_section.replace("{{degree}}", degree if degree else "")
        education_section = education_section.replace("{{university}}", university if university else "")
        education_section = education_section.replace("{{period}}", period if period else "")
        education_section = education_section.replace("{{description}}", description if description else "")
    
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
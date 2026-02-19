import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time 
import random 
import logging
import config
import user_agents
import supabase_utils
import html2text
import json

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Function: Extract Essential Job Content ---
def _extract_essential_job_content(html_content: str) -> str | None:
    """
    Extracts only the essential job content (requirements, responsibilities, qualifications)
    from LinkedIn job description HTML, removing boilerplate, benefits, and unnecessary markup.
    
    This reduces token count sent to AI by 50-70% while maintaining scoring accuracy.
    """
    if not html_content:
        return None
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove style, script tags
        for tag in soup(['style', 'script', 'noscript']):
            tag.decompose()
        
        # Extract text with line breaks preserved
        text = soup.get_text(separator='\n', strip=True)
        
        # Split into lines and filter out very short lines (usually boilerplate)
        lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 15]
        
        # Keep only lines that likely contain job content (avoid "Apply now", "Follow company", etc.)
        important_keywords = ['require', 'skill', 'experience', 'responsibility', 'duty', 'qualification', 
                             'ability', 'knowledge', 'background', 'proficiency', 'expertise', 'role',
                             'about', 'description', 'what', 'you', 'we', 'our', 'technical', 'preferred',
                             'must', 'should', 'will', 'looking', 'seeking', 'need']
        
        # Filter: Keep lines that match important keywords OR are obviously lists/structured content
        filtered_lines = []
        for line in lines:
            lower_line = line.lower()
            # Keep if has important keyword, or is a list item, or is a quality statement
            if any(keyword in lower_line for keyword in important_keywords) or \
               line.startswith('•') or line.startswith('-') or line.startswith('*') or \
               len(line) > 40:  # Longer lines usually have meaningful content
                filtered_lines.append(line)
        
        result = '\n'.join(filtered_lines)
        
        # If we filtered too aggressively, return original
        if len(result) < 100:
            return html2text.html2text(html_content).strip()
        
        return result
        
    except Exception as e:
        logging.warning(f"Error extracting essential job content: {e}. Falling back to full text.")
        return None


# --- LinkedIn Scraping Logic ---
def _fetch_linkedin_job_ids(search_query: str, location: str) -> list:
    """Fetches job IDs from LinkedIn search results pages with delays, rotating user agents, and retries."""

    job_ids_list = []
    start = 0
    max_start = config.LINKEDIN_MAX_START


    logging.info(f"--- Starting Phase 1: Scraping Job IDs (Max Start: {max_start}) ---")
    while start <= max_start:
        # Build URL with proper query string syntax (? for first param, & for rest)
        base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        
        # Build query parameters dict
        params = {
            "keywords": search_query.replace(' ', '+'),
            "location": location,
            "geoId": config.LINKEDIN_GEO_ID,
            "f_TPR": config.LINKEDIN_JOB_POSTING_DATE,
            "f_WT": config.LINKEDIN_F_WT,
            "start": start
        }
        
        # Only add job type filter if specified
        if hasattr(config, 'LINKEDIN_JOB_TYPE') and config.LINKEDIN_JOB_TYPE:
            params["f_JT"] = config.LINKEDIN_JOB_TYPE
        
        # Construct URL with proper syntax: base?param1=val1&param2=val2
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        target_url = f"{base_url}?{query_string}"

        user_agent = random.choice(user_agents.USER_AGENTS)
        headers = {'User-Agent': user_agent}
    
        logging.info(f"Using User-Agent: {user_agent}")

    
        logging.info(f"Scraping URL: {target_url}")

        res = None 
        retries = 0
        while retries <= config.MAX_RETRIES:
            try:
                res = requests.get(target_url, headers=headers, timeout=config.REQUEST_TIMEOUT)
                res.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429 and retries < config.MAX_RETRIES:
                    retries += 1
                    wait_time = config.RETRY_DELAY_SECONDS + random.uniform(0, 5) 
                    
                    logging.warning(f"Error 429: Too Many Requests. Retrying attempt {retries}/{config.MAX_RETRIES} after {wait_time:.2f} seconds...")
                    time.sleep(wait_time)

                    user_agent = random.choice(user_agents.USER_AGENTS)
                    headers = {'User-Agent': user_agent}
                
                    logging.info(f"Retrying with new User-Agent: {user_agent}")
                    continue
                else:
                    
                    logging.error(f"HTTP Error fetching search results page: {e}")
                    res = None 
                    break
            except requests.exceptions.RequestException as e:
                
                logging.error(f"Request Exception fetching search results page: {e}")
                res = None
                break

        
        if res is None:
            logging.error(f"Failed to fetch {target_url} after {retries} retries. Stopping pagination for this query.")
            break 

        if not res.text:
            
             logging.info(f"Received empty response text at start={start}, stopping.")
             break

        soup = BeautifulSoup(res.text, 'html.parser')
        all_jobs_on_this_page = soup.find_all('li')

        if not all_jobs_on_this_page:
            
             logging.info(f"No job listings ('li' elements) found on page at start={start}, stopping.")
             break

    
        logging.info(f"Found {len(all_jobs_on_this_page)} potential job elements on this page.")

        jobs_found_this_iteration = 0
        for job_element in all_jobs_on_this_page:
            base_card = job_element.find("div", {"class": "base-card"})
            job_urn = base_card.get('data-entity-urn') if base_card else None
            if job_urn and 'jobPosting:' in job_urn:
                try:
                    jobid = job_urn.split(":")[3]
                    if jobid not in job_ids_list:
                         job_ids_list.append(jobid)
                         jobs_found_this_iteration += 1
                except IndexError:
                    
                    logging.warning(f"Could not parse job ID from URN: {job_urn}")
                    pass

    
        logging.info(f"Added {jobs_found_this_iteration} unique job IDs from this page.")

        if jobs_found_this_iteration == 0 and len(all_jobs_on_this_page) > 0:
        
            logging.info("Found list items but no new job IDs extracted, potentially end of relevant results or parsing issue.")
            break

        start += 10


    logging.info(f"--- Finished Phase 1: Found {len(job_ids_list)} unique job IDs during scraping ---")
    return job_ids_list

def _fetch_linkedin_job_details(job_id: str) -> dict | None:
    """Fetches detailed information for a single job ID with delays, rotating user agents, and retries."""

    job_detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    logging.info(f"Preparing to fetch details for job ID: {job_id}")

    user_agent = random.choice(user_agents.USER_AGENTS)
    headers = {'User-Agent': user_agent}

    logging.info(f"Using User-Agent for details: {user_agent}")


    logging.info(f"Fetching details from: {job_detail_url}")

    resp = None 
    retries = 0
    while retries <= config.MAX_RETRIES:
        try:
            resp = requests.get(job_detail_url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            break
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and retries < config.MAX_RETRIES:
                retries += 1
                wait_time = config.RETRY_DELAY_SECONDS + random.uniform(0, 5) 
                
                logging.warning(f"Error 429 for job ID {job_id}. Retrying attempt {retries}/{config.MAX_RETRIES} after {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                user_agent = random.choice(user_agents.USER_AGENTS)
                headers = {'User-Agent': user_agent}
            
                logging.info(f"Retrying job {job_id} with new User-Agent: {user_agent}")
                continue
            else:
                
                logging.error(f"HTTP Error fetching details for job ID {job_id}: {e}")
                return None
        except requests.exceptions.RequestException as e:
            
            logging.error(f"Request Exception fetching details for job ID {job_id}: {e}")
            return None 

    
    if resp is None:
         logging.error(f"Failed to fetch details for job ID {job_id} after {retries} retries (unexpected state).")
         return None

    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
        job_details = {"job_id": job_id}

        # --- Extract Company ---
        try:
            company_img = soup.find("div",{"class":"top-card-layout__card"}).find("a").find("img")
            if company_img:
                job_details["company"] = company_img.get('alt').strip()
            if not job_details.get("company"):
                 company_link = soup.find("a", {"class": "topcard__org-name-link"})
                 if company_link:
                      job_details["company"] = company_link.text.strip()
                 else:
                      sub_title_span = soup.find("span", {"class": "topcard__flavor"})
                      if sub_title_span:
                           job_details["company"] = sub_title_span.text.strip()

            if not job_details.get("company"):
                 job_details["company"] = None
                 print(f"Warning: Could not extract company for job ID {job_id}")
        except Exception as e:
            print(f"Error extracting company for job ID {job_id}: {e}")
            job_details["company"] = None

        # --- Extract Job Title ---
        try:
            title_link = soup.find("div",{"class":"top-card-layout__entity-info"}).find("a")
            job_details["job_title"] = title_link.text.strip() if title_link else None
            if not job_details["job_title"]:
                 title_h1 = soup.find("h1", {"class": "top-card-layout__title"})
                 if title_h1:
                      job_details["job_title"] = title_h1.text.strip()
        except Exception as e: 
            print(f"Error extracting job title for job ID {job_id}: {e}")
            job_details["job_title"] = None

        # --- Extract Seniority Level ---
        try:
            # Find all criteria items
            criteria_items = soup.find("ul",{"class":"description__job-criteria-list"}).find_all("li")
            job_details["level"] = None 
            for item in criteria_items:
                header = item.find("h3", {"class": "description__job-criteria-subheader"})
                if header and "Seniority level" in header.text:
                    level_text = item.find("span", {"class": "description__job-criteria-text"})
                    if level_text:
                        job_details["level"] = level_text.text.strip()
                        break 
        except Exception as e: 
            print(f"Error extracting seniority level for job ID {job_id}: {e}")
            job_details["level"] = None

        # --- Extract Location ---
        try:
           
            location_span = soup.find("span", {"class": "topcard__flavor topcard__flavor--bullet"})
            if location_span:
                job_details["location"] = location_span.text.strip()
            else:
                
                subtitle_div = soup.find("div", {"class": "topcard__flavor-row"})
                if subtitle_div:
                    location_span_fallback = subtitle_div.find("span", {"class": "topcard__flavor"})
                    if location_span_fallback:
                         job_details["location"] = location_span_fallback.text.strip()

            if not job_details.get("location"): 
                 job_details["location"] = None
                 print(f"Warning: Could not extract location for job ID {job_id}")
        except Exception as e:
            print(f"Error extracting location for job ID {job_id}: {e}")
            job_details["location"] = None

        # --- Extract Description ---
        raw_description_html = ""
        try:
            description_div = soup.find("div", {"class": "show-more-less-html__markup"})
            if description_div:
                raw_description_html = str(description_div)
            else:
                logging.warning(f"Could not find description div for job ID {job_id}")
        except Exception as e:
            logging.error(f"Error extracting raw description for job ID {job_id}: {e}")
            raw_description_html = ""

        if raw_description_html.strip():
            # Parse HTML and extract only essential job content (requirements, responsibilities)
            # This reduces token count sent to AI for scoring by 50-70%
            essential_description = _extract_essential_job_content(raw_description_html)
            if essential_description:
                job_details["description"] = essential_description
            else:
                # Fallback: use full description if extraction fails
                job_details["description"] = html2text.html2text(raw_description_html).strip()
        else:
            job_details["description"] = None
            logging.warning(f"Raw description was empty for job ID {job_id}.") 

        # --- Set Provider ---
        job_details["provider"] = "linkedin"
        
        return job_details

    except Exception as e:
         
         logging.error(f"General Error processing details for job ID {job_id} after successful fetch: {e}")
         return None

def process_linkedin_query(search_query: str, location: str) -> list:
    """
    Orchestrates scraping and detail fetching for a single query,
    filtering against existing jobs in Supabase BEFORE fetching details.
    Returns a list of new job details found.
    """

    scraped_job_ids = _fetch_linkedin_job_ids(search_query, location)
    if not scraped_job_ids:
    
        logging.info("No job IDs found in Phase 1. Skipping detail fetching.")
        return []

    unique_linkedin_job_ids = list(set(scraped_job_ids))

    logging.info(f"Found {len(scraped_job_ids)} raw job IDs, {len(unique_linkedin_job_ids)} unique IDs after scraping.")


    logging.info("\n--- Starting Filtering Step: Checking against Supabase ---")
    job_ids_set, company_title_set = supabase_utils.get_existing_jobs_from_supabase()

    new_job_ids_to_process = [
        str(job_id) for job_id in unique_linkedin_job_ids 
        if str(job_id) not in job_ids_set
    ]


    logging.info(f"Found {len(unique_linkedin_job_ids)} unique scraped IDs.")

    logging.info(f"Found {len(job_ids_set)} existing IDs in Supabase.")

    logging.info(f"Identified {len(new_job_ids_to_process)} new job IDs to fetch details for.")

    if not new_job_ids_to_process:
    
        logging.info("No new job IDs to process after filtering.")
        return []


    logging.info(f"\n--- Starting Phase 2: Fetching Job Details for {len(new_job_ids_to_process)} New IDs ---")
    detailed_new_jobs = []
    processed_count = 0

    ids_to_fetch = new_job_ids_to_process

    for job_id in ids_to_fetch:
        details = _fetch_linkedin_job_details(job_id)
        if details:
            description = details.get('description')
            if description and description.strip(): 
                if 'job_id' in details and details['job_id'] is not None:
                    detailed_new_jobs.append(details)
                    processed_count += 1
                else:
                    
                    logging.warning(f"Fetched details for {job_id} but missing 'job_id' key. Skipping.")
            else:
                
                logging.warning(f"Skipping job ID {job_id} due to missing or empty description.") 
        else:
            
            logging.warning(f"Skipping job ID {job_id} as detail fetching failed or returned no data.") 


    logging.info(f"--- Finished Phase 2: Successfully fetched details for {processed_count} new job(s) ---")
    return detailed_new_jobs

# --- Main Execution ---

if __name__ == "__main__":

    total_new_jobs_saved = 0

    # Get jobs from LinkedIn
    logging.info("\n--- Starting LinkedIn Job Scraping ---")
    for query in config.LINKEDIN_SEARCH_QUERIES:
        print(f"\n{'='*20} Processing Search Query: '{query}' {'='*20}")

        # 1. Process the query: Scrape IDs, filter, fetch new details
        new_linkedin_job_details = process_linkedin_query(query, config.LINKEDIN_LOCATION)

        # 2. Save the NEW scraped data to Supabase
        if new_linkedin_job_details:
            print(f"\n--- Saving {len(new_linkedin_job_details)} new job(s) for query '{query}' ---")
            supabase_utils.save_jobs_to_supabase(new_linkedin_job_details)
            total_new_jobs_saved += len(new_linkedin_job_details)
        else:
            print(f"\nNo new job details were fetched or processed for query '{query}'.")

    # --- End of Script ---      
    logging.info(f"\n{'='*20} Job scraping script finished {'='*20}")
    logging.info(f"Total new jobs saved across all queries: {total_new_jobs_saved}")
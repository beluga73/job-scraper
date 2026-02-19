import os
from dotenv import load_dotenv

load_dotenv()

# --- DO NOT MODIFY THE BELOW SECTION ---

# --- Supabase Configuration ---
SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_TABLE_NAME: str = "jobs"
SUPABASE_RESUME_TABLE_NAME = "resumes"
SUPABASE_CUSTOMIZED_RESUMES_TABLE_NAME = "customized_resumes"
SUPABASE_STORAGE_BUCKET="resumes"

# --- OpenAI Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL_NAME = "gpt-4o"  # Using GPT-4 Omni for best quality and cost-effectiveness

# --- Resume Scoring Configuration ---
JOBS_TO_SCORE_PER_RUN = 10 # Limit jobs processed per script execution (respects API limits)
OPENAI_REQUEST_DELAY_SECONDS = 6 # Delay between OpenAI API calls

# --- LinkedIn Configuration ---
LINKEDIN_EMAIL = os.environ.get("LINKEDIN_EMAIL")


# --- Scraping Parameters ---
LINKEDIN_MAX_START = 30 # Reduced for 40 Jobs ids
REQUEST_TIMEOUT = 30 # Timeout for HTTP requests in seconds
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 15

# --- Job Management Parameters ---
JOB_EXPIRY_DAYS = 30 # Mark jobs as expired after this many days if not applied/interviewing etc.
JOB_CHECK_DAYS = 3   # Check if a job is still active if last_checked is older than this
JOB_DELETION_DAYS = 60 # Delete inactive ('expired', 'removed') jobs older than this
JOB_CHECK_LIMIT = 50 # Max number of jobs to check for activity per run
ACTIVE_CHECK_TIMEOUT = 20 # Timeout for checking if a job is active
ACTIVE_CHECK_MAX_RETRIES = 2
ACTIVE_CHECK_RETRY_DELAY = 10 # Base delay for retrying active check

# --- DO NOT MODITY THE ABOVE SECTION ---

# --- LinkedIn Search Configuration ---
LINKEDIN_SEARCH_QUERIES = ["fullstack developer", "frontend developer", "react developer", "backend developer", "node.js developer", "full stack web developer"]
LINKEDIN_LOCATION = "Poland"
LINKEDIN_GEO_ID = 105072130 # Poland
# LINKEDIN_JOB_TYPE = "F" # Commented out to include all job types (full-time, part-time, contract, etc.)
LINKEDIN_JOB_POSTING_DATE = "r86400" # Past 24 hours
LINKEDIN_F_WT=3,2,1 #3=Hybrid, 2=Remote, 1=Onsite

#  --- Careers Future Search Configuration - REMOVED (Singapore only) ---
# CAREERS_FUTURE_SEARCH_QUERIES = ["Fullstack Developer", "Frontend Developer", "React Developer", "Backend Developer", "Node.js Developer", "Full Stack Web Developer"]
# CAREERS_FUTURE_SEARCH_CATEGORIES = ["Information Technology"]
# CAREERS_FUTURE_SEARCH_EMPLOYMENT_TYPES = ["Full Time"]


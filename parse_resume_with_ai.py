"""
Stage 2: AI-Powered Resume Parser
This module takes extracted resume text and uses AI to parse it into structured data.
"""

import json
import os
from openai import OpenAI
from typing import List, Optional
import models


def parse_resume_with_ai(client: OpenAI, resume_text):
    """
    Send resume text to OpenAI and get structured information back.
    
    Args:
        client (OpenAI): OpenAI client instance
        resume_text (str): The plain text extracted from the resume
        
    Returns:
        dict: Structured resume information
    """
    print("Processing resume with OpenAI...")

    prompt = f"""Extract and return the structured resume information from the text below. Only use what is explicitly stated in the text and do not infer or invent any details.

    Resume text:
    {resume_text}
    """

    response = client.beta.messages.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format=models.Resume,
    )
    
    # Extract the parsed content
    parsed_resume = response.content[0].parsed
    return json.dumps(parsed_resume.model_dump(), indent=2)

"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys for direct access
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Council members - list of model identifiers
# Format: "provider/model-name"
COUNCIL_MODELS = [
    "openai/gpt-5",
    "google/gemini-3-pro-preview",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Data directory for conversation storage
DATA_DIR = "data/conversations"


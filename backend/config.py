"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys for direct access
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://uvcqfhwcvxtasgokihic.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV2Y3FmaHdjdnh0YXNnb2tpaGljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU4OTM5MTMsImV4cCI6MjA4MTQ2OTkxM30.E7m_s-C5XzB2ZgiwewyBl8LwYr2rxa09txvky0kCVfI")

# Council members - list of model identifiers
# Format: "provider/model-name"
COUNCIL_MODELS = [
    "openai/gpt-5",
    "google/gemini-3-pro-preview",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Data directory for conversation storage (fallback)
DATA_DIR = "data/conversations"



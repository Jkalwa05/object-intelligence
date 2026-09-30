from dotenv import load_dotenv

# Lets `pytest -m claude` find the API key in .env; never overrides real environment variables.
load_dotenv(override=False)

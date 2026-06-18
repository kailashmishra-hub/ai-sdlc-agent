# AI SDLC Streamlit App

This project is a Streamlit-only AI SDLC generator. Users provide their own OpenAI API key in the UI at runtime; no OpenAI API key needs to be stored in GitHub or Streamlit Cloud secrets.

## Run locally

```powershell
cd C:\Users\Kailash\OneDrive\Documents\AI_SDLC
pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

## API Key

For local personal use, you may create a `.env` file or set environment variables:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

For deployed use, do not store an API key if each user should pay with their own key. The app will show a password input when no key is configured.

The app does not use fallback/sample generation. If no API key is provided or a model response is invalid, generation stops with an error.

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to Streamlit Community Cloud.
3. Create a new app from the GitHub repository.
4. Set the main file path to:

```text
app.py
```

5. Leave Streamlit secrets empty if users will enter their own OpenAI API key.

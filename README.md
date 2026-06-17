# AI SDLC Platform

Hackathon-ready AI SDLC Platform built with Python, Streamlit, LangGraph, OpenAI GPT models, and ChromaDB.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

The app accepts PDF, TXT, and image uploads, extracts content, stores chunks in ChromaDB, runs the SDLC agents, and writes all generated artifacts under:

```text
<Output Directory>\<Project Name>_<Timestamp>
```

OpenAI is optional for demos. If no API key is provided, the app generates deterministic sample artifacts from the uploaded content.

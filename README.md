# Voice AI Receptionist 🎙️🤖

An intelligent voice AI receptionist application built with FastAPI, SQLAlchemy, and modern conversational AI pipelines.

---

## 📁 Project Structure

```text
voice-ai-receptionist/
│
├── app/
│   ├── __init__.py       # App package initialization
│   ├── main.py           # FastAPI application entry point & routes
│   ├── database.py       # SQLAlchemy engine and session setup
│   ├── models.py         # Database and Pydantic schemas (Contacts, Calls, Appointments)
│   └── services.py       # Voice AI orchestration (STT, LLM conversation, TTS)
│
├── .env                  # Environment variables (local secret keys)
├── .env.example          # Sample environment variables template
├── requirements.txt      # Project dependencies
└── README.md             # Documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- (Optional) Twilio account and OpenAI / ElevenLabs API keys

### 2. Setup Virtual Environment

```bash
# Navigate to the project directory
cd voice-ai-receptionist

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
```

### 5. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access the interactive API documentation at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)


# ⚡ OmniQuest v0

**Play the live demo:** [https://omni-quest-v0.vercel.app](https://omni-quest-v0.vercel.app)

OmniQuest is an AI-powered, gamified learning gauntlet. This repository holds **Version 0 (v0)**—the foundational base model of the game engine. 

While there are countless basic quiz generators on the internet, OmniQuest is built with a proper full-stack architecture. It features a custom FastAPI backend, strict server-side answer validation to prevent cheating, and an automated fallback system to ensure the application never crashes during API rate limits.

## 🚀 The Vision: Why v0?
This version is the core engine. It proves the foundational mechanics: dynamic AI prompt generation, strict JSON data validation, and tiered progression. 

This is just the beginning. **Future updates (v1 and beyond) will introduce:**
* Fully functional tactical power-ups (AI Hint, Time Freeze, 50/50).
* Streak multipliers and advanced Insight Points (IP) scoring.
* User authentication and global leaderboards.
* Multiplayer and head-to-head challenges.

## 🛠️ Tech Stack
* **Frontend:** Next.js, React, Tailwind CSS (Deployed on Vercel)
* **Backend:** Python, FastAPI (Deployed on Render)
* **AI Engine:** Google Gemini Flash (via the official `google-genai` SDK)

## ✨ Core v0 Features
* **Dynamic Gauntlet:** Generates a 20-stage MCQ progression on any topic on the fly.
* **Tiered Progression:** 4 difficulty tiers. Players must earn enough Insight Points in the current tier to unlock the next one.
* **Server-Side Security:** Correct answers are never exposed in the frontend payload. The Python backend validates player guesses in real-time.
* **Crash-Proof Fallback:** If the AI API times out or hits a high-demand 503 error, the backend silently serves a pre-validated, hardcoded sample round so the game session stays alive.

## 💻 Run it Locally

### 1. Backend Engine
```bash
cd backend
python -m venv .venv
# Activate venv (Windows: .\.venv\Scripts\activate | Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# Set your API key
# Windows PowerShell: $env:GEMINI_API_KEY="your_api_key_here"
# Mac/Linux: export GEMINI_API_KEY="your_api_key_here"

python -m uvicorn main:app --reload
```

### 2. Frontend UI
```bash
cd frontend
npm install
npm run dev
```
*The frontend runs on `localhost:3000` and defaults to calling the backend at `localhost:8000`.*
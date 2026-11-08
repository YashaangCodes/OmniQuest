# ⚡ OmniQuest v0.9

**Play the live demo:** [https://omniquest-ai.vercel.app](https://omniquest-ai.vercel.app)

OmniQuest is an AI-powered, adaptive multiple-choice gauntlet that generates a dynamic learning ladder (5, 10, 15, or 20 stages) on absolutely any topic you type or uploaded document (PDF, DOCX, PPTX, TXT). 

**Version 0.9 (Pre-Release / Beta)** represents a major architectural upgrade from the initial v0 MVP and v0.5 milestone, focusing heavily on gameplay fairness, UI/UX polish, difficulty-based power-up allocation, server-authoritative scoring and timing security, and robust document extraction.

### Roadmap

**Coming in v1.0:** Full OCR support for scanned and image-based document uploads.

## 🛠 The Evolution: Gaps in v0 & How We Fixed Them

Building an AI-generated game introduced several unpredictable edge cases. Here is how v0.5 addresses the biggest gaps from the initial launch:

### 1. The "Spotify Problem" (AI Option Bias)
* **The Gap:** In v0, the AI heavily favoured placing the correct answer in Option B (up to 40% of the time). When we initially applied true mathematical randomness (`random.shuffle`), it created annoying statistical clumps (e.g., the correct answer being B four times in a row). 
* **The Fix:** Implemented a **Bounded Randomness Algorithm** in Python. The backend now pre-generates a 20-position array with strict mathematical limits: the correct answer can never appear in the same slot more than *twice consecutively*, and no single slot can hold the correct answer more than *7 times total*. It is perfectly balanced but impossible to card-count.

### 2. The API Spam & Gibberish Inputs
* **The Gap:** Users could type "....." or "asdfghjkl", bypassing basic empty-string checks and forcing the AI to hallucinate random general knowledge questions, wasting API quota.
* **The Fix:** Built a **Two-Layer Validation System**. First, deterministic Python validation ensures the input contains at least one actual alphanumeric character (blocking punctuation spam). Second, a single-pass AI Semantic Validation forces Gemini to evaluate if the topic is real before generating the gauntlet, returning a clean HTTP 400 if the topic is uninterpretable.

### 3. The "Blink-and-Miss" Explanations
* **The Gap:** After submitting an answer, v0 used a strict 2-second `setTimeout` before automatically jumping to the next stage. Players couldn't actually read the AI's explanations.
* **The Fix:** **Manual Stage Progression.** The timer now completely freezes after an answer is submitted, and the game patiently waits for the player to click a prominent "Next Stage" button, allowing unlimited time to read the facts.

### 4. The Scrolling Nightmare
* **The Gap:** On mobile devices, long AI-generated questions pushed the power-up buttons off the screen, forcing players to scroll up and down constantly while a 20-second timer was ticking.
* **The Fix:** Completely rebuilt the Next.js gameplay arena using a **Fixed Viewport Architecture** (`h-dvh max-h-dvh overflow-hidden`). The top stats bar and bottom power-ups bar are now permanently anchored, while only the center question card scrolls internally. Zero page-level scrolling required.

## ✨ Core Features in v0.9
- **Dynamic Gauntlet Lengths:** Choose between 5, 10, 15, or 20 questions with automatic tier mapping and checkpoints.
- **Document-Based Gauntlets:** Upload PDF, DOCX, PPTX, or TXT documents for text-based extraction in "Strict Material Only" or "AI Enhanced" modes.
- **Server-Authoritative Timing:** Monotonic clock timing on the backend with 20-second question windows, 5-second Time Freeze extensions, and automatic deadline enforcement to prevent client timing manipulation.
- **Difficulty-Based Power-Up Limits:** Strict quotas per difficulty (Easy: 2 hints, 2 fifty-fifties, 2 freezes; Medium: 1 hint, 1 fifty-fifty, 2 freezes; Hard: 2 freezes; Expert: no power-ups).
- **Difficulty-Based Tier Progression:** Tier advancement requiring specific local IP thresholds depending on chosen difficulty (Easy, Medium, Hard, Expert).
- **Dual-Input Engine:** Players can define a Topic (e.g., "Physics") AND a Target Level/Context (e.g., "10th Grade" or "Pop Culture").
- **Forfeit Run:** Allows players to end a run early while preserving accumulated Insight Points and routing directly to post-game analytics.
- **"How to Play" Modal:** Explains Insight Points mechanics, Speed Bonus, Streak Fire, and Tier checkpoints.

## 💻 Tech Stack
- **Frontend:** Next.js 14, React, Tailwind CSS, TypeScript
- **Backend:** Python 3, FastAPI, Uvicorn
- **AI Engine:** Google Gemini API
- **Deployment:** Vercel (Frontend) / Render (Backend)

## 🚀 Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YourUsername/OmniQuest.git
   ```
2. **Start the Backend:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/Scripts/activate # or source .venv/bin/activate on Mac/Linux
   pip install -r requirements.txt
   # Ensure you have your GEMINI_API_KEY set in your environment
   python -m uvicorn main:app --reload
   ```
3. **Start the Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Open `http://localhost:3000` in your browser.

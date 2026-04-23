# Task 2 — Fix: summary, step-by-step, and key concepts not returning

## Symptom
The `/summarize` endpoint returns the transcript correctly but `summary`, `steps`, and `concepts` come back empty. The frontend shows the Transcript tab with content but the other three tabs are blank.

## Where to look — `backend/app.py`

### 1. Check the AI prompt is actually requesting all fields
The prompt sent to the AI provider must explicitly ask for `summary`, `steps`, and `concepts` and instruct the model to return them as structured JSON. Look for the prompt string and verify it contains instructions for all three fields. A prompt that only asks for a summary will only return a summary.

The prompt should include something like:
```
Return ONLY a JSON object with these exact keys:
{
  "summary": "...",
  "steps": ["step 1", "step 2", ...],
  "concepts": [{"name": "...", "description": "...", "url": ""}],
  "verdict": "...",
  "title": "..."
}
Do not include any text outside the JSON object.
```

### 2. Check the JSON parsing
After the AI response comes back, the code must parse the JSON and extract all fields. Look for where `data.content` is parsed. Common failure modes:
- The model wraps its response in ```json ... ``` fences — strip them before `json.loads()`
- The code only reads `response["summary"]` and never reads `steps` or `concepts`
- A `KeyError` is silently swallowed and the fields default to empty

Add explicit fallback extraction:
```python
import json, re

def extract_json(text):
    # Strip markdown code fences if present
    text = re.sub(r'^```json\s*', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text.strip(), flags=re.MULTILINE)
    return json.loads(text)
```

### 3. Check the response model
The `TranscriptResponse` Pydantic model should have `steps: list = []` and `concepts: list = []`. If they're missing from the model, FastAPI strips them from the response even if the AI returned them.

### 4. Check the frontend reads all fields
In `frontend/index.html`, search for where `data.steps` and `data.concepts` are read after the fetch call. If the JS only reads `data.summary`, the other tabs will always be empty regardless of what the backend returns.

## How to verify the fix
Add a temporary `print()` or `logging.info()` right after the AI response is parsed, logging the raw response text and the extracted dict. Check Railway logs after a test summarisation — you should see all four fields populated.

## Acceptance criteria
- All four tabs (Summary, Step-by-Step, Key Concepts, Transcript) populate correctly after a summarisation
- Works across at least two providers (e.g. OpenAI + Groq)
- No silent exception swallowing — errors must be logged

# Testing AidCare Triage System

This guide explains how to test the AidCare triage functionality with the updated Gemini 3 models.

## Prerequisites

1. **Backend server must be running**
2. **Environment variables configured** (`.env` file with `GOOGLE_API_KEY`)
3. **Python 3.8+** installed
4. **Required packages** installed (`requests`)

## Quick Start

### 1. Start the Backend Server

```bash
cd aidcare-backend
uvicorn main:app --reload
```

The server should start at `http://localhost:8000`

You should see:
- ✓ Whisper model loading
- ✓ CHW Retriever initialized
- ✓ Clinical Retriever initialized

### 2. Run the Test Script

In a new terminal:

```bash
cd aidcare-backend
python test_triage.py
```

This will:
- Check server health
- Run 3 test cases with different medical scenarios
- Display extracted symptoms, guidelines, and recommendations
- Show which Gemini models were used

## Testing Methods

### Method 1: Automated Test Script (Recommended)

```bash
python test_triage.py
```

**Features:**
- Tests multiple scenarios automatically
- Shows detailed output for each step
- Validates server health first
- Includes timing information

### Method 2: Using cURL

Test a single case with cURL:

```bash
curl -X POST "http://localhost:8000/triage/process_text/" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript_text": "Patient has fever and cough for 2 days. Temperature is 39 degrees."
  }'
```

### Method 3: Using Python Requests

```python
import requests
import json

url = "http://localhost:8000/triage/process_text/"
data = {
    "transcript_text": "Patient has chest pain and shortness of breath."
}

response = requests.post(url, json=data)
print(json.dumps(response.json(), indent=2))
```

### Method 4: Using FastAPI Swagger UI

1. Start the server
2. Open browser: `http://localhost:8000/docs`
3. Find the `/triage/process_text/` endpoint
4. Click "Try it out"
5. Enter test transcript
6. Click "Execute"

### Method 5: Using the Frontend (PWA)

1. Start the backend server (port 8000)
2. Start the frontend:
   ```bash
   cd aidcare-pwa
   npm run dev
   ```
3. Open browser: `http://localhost:3000`
4. Navigate to the Triage section
5. Enter patient information or record audio
6. Submit to see results

## What to Expect

### Successful Response Structure

```json
{
  "mode": "chw_triage_text_input",
  "input_transcript": "...",
  "extracted_symptoms": ["fever", "cough", "difficulty breathing"],
  "retrieved_guidelines_summary": [
    {
      "source": "CHEW Guidelines",
      "code": "2.3",
      "case": "Child with fever",
      "score": 0.45
    }
  ],
  "triage_recommendation": {
    "summary_of_findings": "Child presenting with fever...",
    "recommended_actions_for_chw": [
      "1. Measure temperature",
      "2. Assess for danger signs",
      "3. Provide appropriate treatment"
    ],
    "urgency_level": "Refer to Clinic for Assessment",
    "key_guideline_references": ["Code: 2.3, Case: Child with fever"],
    "important_notes_for_chw": ["Monitor closely", "Check for complications"]
  }
}
```

## Verifying Gemini 3 Models

Check the server logs for model confirmation:

```
CHW Mode - Starting Phase 3: Symptom Extraction...
Using model: gemini-3-flash-preview

CHW Mode - Starting Phase 5: Recommendation Generation...
Using model: gemini-3-flash-preview
```

## Test Cases Included

1. **Child with Fever and Cough**
   - Tests pediatric triage
   - Tests multiple symptoms
   - Expected: Urgent referral recommendation

2. **Adult with Chest Pain**
   - Tests cardiac symptoms
   - Tests with medical history
   - Expected: Immediate referral recommendation

3. **Headache and Fatigue**
   - Tests general symptoms
   - Tests symptom duration tracking
   - Expected: Clinic assessment recommendation

## Troubleshooting

### Server Not Starting

**Problem:** `uvicorn: command not found`
**Solution:**
```bash
pip install uvicorn fastapi
```

**Problem:** Database connection error
**Solution:** Check `DATABASE_URL` in `.env` or temporarily disable DB operations

### API Errors

**Problem:** 503 Error - "CHW Triage knowledge base not available"
**Solution:** Ensure the retriever indices are built:
```bash
cd aidcare-backend
python -m aidcare_pipeline.build_index  # if this script exists
```

**Problem:** 500 Error - Gemini API error
**Solution:**
- Check `GOOGLE_API_KEY` in `.env`
- Verify API key is valid at https://ai.google.dev
- Check rate limits

**Problem:** Empty or incorrect results
**Solution:**
- Check model names in `.env` match available models
- Verify transcripts contain medical information
- Check server logs for detailed error messages

### Test Script Issues

**Problem:** `requests` module not found
**Solution:**
```bash
pip install requests
```

**Problem:** Connection refused
**Solution:** Ensure backend server is running on port 8000

## Performance Notes

- **gemini-3-flash-preview**: ~2-5 seconds per request (symptom extraction + recommendations)
- **gemini-3-pro-preview**: ~5-10 seconds per request (clinical support operations)

The mixed approach balances speed (Flash for triage) and accuracy (Pro for clinical decisions).

## Advanced Testing

### Test with Audio File

```bash
curl -X POST "http://localhost:8000/triage/process_audio/" \
  -F "audio_file=@/path/to/consultation.wav"
```

### Test Clinical Support Mode

```bash
curl -X POST "http://localhost:8000/clinical_support/process_consultation/" \
  -F "audio_file=@/path/to/consultation.wav" \
  -F "manual_context=Patient has history of hypertension"
```

## Monitoring Model Usage

Check which models are being used in real-time:

```bash
# In server terminal
tail -f logs/aidcare.log  # if logging to file

# Or watch server output for lines like:
# "Sending request to Gemini model 'gemini-3-flash-preview'..."
# "Sending request to Gemini model 'gemini-3-pro-preview'..."
```

## Need Help?

- Check server logs for detailed error messages
- Verify all environment variables are set correctly
- Ensure all required Python packages are installed
- Check that the knowledge base indices are built and loaded

## Next Steps

After successful testing:
1. Test with real consultation audio recordings
2. Validate recommendations against actual guidelines
3. Test edge cases (no symptoms, unclear speech, etc.)
4. Monitor API usage and costs
5. Test the full PWA interface

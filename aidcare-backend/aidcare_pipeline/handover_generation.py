# aidcare_pipeline/handover_generation.py
import google.generativeai as genai
import json
import os
import time

GEMINI_MODEL_HANDOVER = os.getenv("GEMINI_MODEL_HANDOVER", "gemini-2.0-flash-exp")

_MODERN_GEMINI_PREFIXES = ("gemini-1.5", "gemini-2", "gemini-3")

_FALLBACK_HANDOVER_RESPONSE = {
    "critical_patients": [],
    "stable_patients": [],
    "discharged_patients": [],
    "overall_shift_notes": "",
}


def generate_handover_report(
    consultations: list,
    doctor_name: str,
    ward: str,
    shift_start: str,
    shift_end: str,
) -> dict:
    """
    Generates a prioritised shift handover report from a list of consultation dicts.

    Args:
        consultations: List of dicts, each containing:
                       patient_ref, soap_note (dict with subjective/objective/assessment/plan),
                       complexity_score (int 1-5), flags (list of str), patient_summary (str).
        doctor_name:   Full name of the outgoing doctor.
        ward:          Ward name/identifier.
        shift_start:   ISO timestamp string or formatted string for shift start.
        shift_end:     ISO timestamp string or formatted string for shift end.

    Returns:
        dict with keys:
            critical_patients   -> [{patient_ref, summary, action_required, flags}]
            stable_patients     -> [{patient_ref, summary}]
            discharged_patients -> [{patient_ref, summary}]
            overall_shift_notes -> str
        Falls back to empty-field dict on any error.
    """
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        print("ERROR (handover_generation): GOOGLE_API_KEY not found in environment.")
        return {**_FALLBACK_HANDOVER_RESPONSE, "error": "Configuration error: Missing Google API Key."}

    if not consultations:
        print("Handover Gen - No consultations provided; returning empty report.")
        return {
            **_FALLBACK_HANDOVER_RESPONSE,
            "overall_shift_notes": f"No consultations recorded for this shift ({shift_start} - {shift_end}).",
        }

    # Build a structured summary of each consultation for the prompt
    consultation_summaries = []
    for i, c in enumerate(consultations, start=1):
        soap = c.get("soap_note", {})
        entry = (
            f"Patient {i}: {c.get('patient_ref', 'Unknown')}\n"
            f"  Summary: {c.get('patient_summary', 'N/A')}\n"
            f"  Complexity: {c.get('complexity_score', 'N/A')}/5\n"
            f"  Flags: {', '.join(c.get('flags', [])) or 'None'}\n"
            f"  SOAP Assessment: {soap.get('assessment', 'N/A')}\n"
            f"  SOAP Plan: {soap.get('plan', 'N/A')}"
        )
        consultation_summaries.append(entry)

    consultations_text = "\n\n".join(consultation_summaries)

    system_instruction = (
        "You are a clinical handover assistant. "
        "Generate a prioritized shift handover report for Nigerian hospital doctors. "
        "Classify patients by acuity: critical (immediate attention needed), "
        "stable (routine monitoring), or discharged (sent home/transferred). "
        "Use clear, concise clinical language appropriate for doctor-to-doctor handover. "
        "The output must be a valid JSON object with no additional text."
    )

    prompt = f"""
Shift Handover Details:
  Doctor: {doctor_name}
  Ward: {ward}
  Shift: {shift_start} to {shift_end}
  Total Patients Seen: {len(consultations)}

Patient Consultation Records:
{consultations_text}

Task:
Review all patient records above and generate a prioritised handover report.

Return ONLY a single valid JSON object with the following keys:
- "critical_patients": [
    {{
      "patient_ref": "<patient identifier>",
      "summary": "<concise clinical summary>",
      "action_required": "<specific action the incoming doctor must take>",
      "flags": ["<flag1>", "<flag2>"]
    }}
  ]
  (Patients with complexity >= 4, urgent flags, or requiring immediate intervention)

- "stable_patients": [
    {{
      "patient_ref": "<patient identifier>",
      "summary": "<brief status and ongoing plan>"
    }}
  ]
  (Patients who are clinically stable and require routine monitoring)

- "discharged_patients": [
    {{
      "patient_ref": "<patient identifier>",
      "summary": "<reason for discharge or transfer and any follow-up instructions>"
    }}
  ]
  (Patients who were discharged, transferred, or signed out this shift)

- "overall_shift_notes": "<free-text paragraph summarising the overall shift, any ward-level concerns,
   resource issues, or important contextual notes for the incoming team>"

Return ONLY the JSON object. Do not include any text before or after it.
JSON Response:
"""

    generation_config = genai.types.GenerationConfig(
        temperature=0.2,
        max_output_tokens=3000,
    )

    max_retries = 2
    raw_json_str = ""

    for attempt in range(max_retries):
        try:
            print(f"Handover Gen - Attempt {attempt + 1} using model '{GEMINI_MODEL_HANDOVER}'...")

            if GEMINI_MODEL_HANDOVER.startswith(_MODERN_GEMINI_PREFIXES):
                model_to_use = genai.GenerativeModel(
                    GEMINI_MODEL_HANDOVER,
                    system_instruction=system_instruction,
                    generation_config=generation_config,
                )
                full_prompt = prompt
            else:
                model_to_use = genai.GenerativeModel(
                    GEMINI_MODEL_HANDOVER,
                    generation_config=generation_config,
                )
                full_prompt = system_instruction + "\n\n" + prompt

            response = model_to_use.generate_content(full_prompt)

            raw_json_str = ""
            if hasattr(response, "text") and response.text:
                raw_json_str = response.text.strip()
            elif response.parts:
                raw_json_str = response.parts[0].text.strip()
            else:
                print(f"Handover Gen - Warning: Gemini response has no text or parts (Attempt {attempt + 1}). Response: {response}")

            # Clean markdown fences
            if raw_json_str.startswith("```json"):
                raw_json_str = raw_json_str[len("```json"):]
            if raw_json_str.startswith("```"):
                raw_json_str = raw_json_str[len("```"):]
            if raw_json_str.endswith("```"):
                raw_json_str = raw_json_str[: -len("```")]
            raw_json_str = raw_json_str.strip()

            print(f"Handover Gen - Raw Gemini response snippet (Attempt {attempt + 1}): {raw_json_str[:300]}...")

            if not raw_json_str:
                if attempt < max_retries - 1:
                    print(f"Handover Gen - Gemini returned empty string, retrying (Attempt {attempt + 1})...")
                    time.sleep(1 * (attempt + 1))
                    continue
                print("Handover Gen - Gemini returned an empty string after retries.")
                return {**_FALLBACK_HANDOVER_RESPONSE, "error": "Gemini returned an empty response."}

            parsed = json.loads(raw_json_str)

            # Validate and fill missing keys with defaults
            expected_keys = ["critical_patients", "stable_patients", "discharged_patients", "overall_shift_notes"]
            for key in expected_keys:
                if key not in parsed:
                    print(f"Handover Gen - Warning: Response missing key '{key}'. Filling with default.")
                    parsed[key] = [] if key != "overall_shift_notes" else ""

            return parsed

        except json.JSONDecodeError as e:
            print(f"Handover Gen - JSONDecodeError (Attempt {attempt + 1}): '{raw_json_str[:200]}'. Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {
                **_FALLBACK_HANDOVER_RESPONSE,
                "error": f"Failed to decode JSON for handover report after retries. Last snippet: {raw_json_str[:200]}",
            }
        except Exception as e:
            print(f"Handover Gen - Exception (Attempt {attempt + 1}): {e}")
            import traceback
            traceback.print_exc()
            if (
                "rate limit" in str(e).lower()
                or "quota" in str(e).lower()
                or "429" in str(e).lower()
                or "resource has been exhausted" in str(e).lower()
            ):
                print("Handover Gen - Rate limit / quota error detected.")
                if attempt < max_retries - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
            elif attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {**_FALLBACK_HANDOVER_RESPONSE, "error": f"Unhandled error during handover generation: {str(e)}"}

    return {**_FALLBACK_HANDOVER_RESPONSE, "error": "Failed handover generation after all retries."}


# ---------------------------------------------------------------------------
# Plain-text formatter (for WhatsApp sharing)
# ---------------------------------------------------------------------------

def generate_plain_text_report(
    report_json: dict,
    doctor_name: str,
    ward: str,
    shift_start: str,
    shift_end: str,
    patients_seen: int,
) -> str:
    """
    Converts a handover report JSON dict to formatted plain text suitable for
    sharing via WhatsApp or printing.

    Args:
        report_json:    The structured handover dict from generate_handover_report.
        doctor_name:    Name of the outgoing doctor.
        ward:           Ward name/identifier.
        shift_start:    Formatted shift start string.
        shift_end:      Formatted shift end string.
        patients_seen:  Total patients seen this shift.

    Returns:
        Formatted plain-text string.
    """
    lines = []
    separator = "=" * 45

    lines.append(separator)
    lines.append("  SHIFT HANDOVER REPORT — AIDCARE COPILOT")
    lines.append(separator)
    lines.append(f"Doctor  : {doctor_name}")
    lines.append(f"Ward    : {ward}")
    lines.append(f"Shift   : {shift_start}  →  {shift_end}")
    lines.append(f"Patients: {patients_seen} seen this shift")
    lines.append("")

    # Critical patients
    critical = report_json.get("critical_patients", [])
    lines.append(f"🔴 CRITICAL PATIENTS ({len(critical)})")
    lines.append("-" * 40)
    if critical:
        for p in critical:
            lines.append(f"  [{p.get('patient_ref', 'Unknown')}]")
            lines.append(f"  Summary : {p.get('summary', '')}")
            lines.append(f"  ACTION  : {p.get('action_required', '')}")
            flags = p.get("flags", [])
            if flags:
                lines.append(f"  Flags   : {', '.join(flags)}")
            lines.append("")
    else:
        lines.append("  None")
        lines.append("")

    # Stable patients
    stable = report_json.get("stable_patients", [])
    lines.append(f"🟡 STABLE PATIENTS ({len(stable)})")
    lines.append("-" * 40)
    if stable:
        for p in stable:
            lines.append(f"  [{p.get('patient_ref', 'Unknown')}]")
            lines.append(f"  {p.get('summary', '')}")
            lines.append("")
    else:
        lines.append("  None")
        lines.append("")

    # Discharged patients
    discharged = report_json.get("discharged_patients", [])
    lines.append(f"🟢 DISCHARGED / TRANSFERRED ({len(discharged)})")
    lines.append("-" * 40)
    if discharged:
        for p in discharged:
            lines.append(f"  [{p.get('patient_ref', 'Unknown')}]")
            lines.append(f"  {p.get('summary', '')}")
            lines.append("")
    else:
        lines.append("  None")
        lines.append("")

    # Overall shift notes
    shift_notes = report_json.get("overall_shift_notes", "")
    if shift_notes:
        lines.append("📋 OVERALL SHIFT NOTES")
        lines.append("-" * 40)
        lines.append(shift_notes)
        lines.append("")

    lines.append(separator)
    lines.append("  Generated by AidCare Copilot")
    lines.append(separator)

    return "\n".join(lines)

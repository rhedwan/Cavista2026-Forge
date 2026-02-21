# AidCare Demo Script

Use this script when demonstrating or testing the application. It tells you exactly what to say and do for each feature.

---

## Before You Start

1. Open the app (localhost:3000 or your deployed URL)
2. Log in: **chioma@lasuth.ng** / **demo1234**
3. Ensure microphone access is allowed when prompted

---

## Demo 1: Triage (Multilingual Patient Intake)

**What it does:** A nurse/CHW conducts triage with a patient in their preferred language. The AI asks questions, the patient responds (text or voice), and the system produces a triage recommendation.

### Scenario A: English – Child with Fever

1. Go to **Triage**
2. Select **English**
3. AI greets you. **Type or say:**
   > "My 4-year-old son has had fever for two days. It goes up to 39 degrees. He also has a bad cough and is not eating well."
4. AI asks follow-up. **Type or say:**
   > "Yes, he seems to breathe a bit fast when he sleeps."
5. (Optional) Add staff note: `Temp 39.2°C, RR 28, SpO2 96%`
6. Click **Complete Assessment**
7. **Check:** Urgency level, risk level, extracted symptoms, and recommended actions appear
8. Click **Assign to Patient Record** → pick a patient → confirm

### Scenario B: Pidgin – Adult with Headache

1. Click **New Triage**
2. Select **Pidgin (Naija Pidgin)**
3. AI greets in Pidgin. **Type or say (in Pidgin or English):**
   > "Belle dey pain me and head dey bang me since yesterday. I no fit sleep."
4. AI responds. **Type or say:**
   > "I dey feel hot, temperature high. I never chop since morning."
5. Add staff note: `BP 140/90, Temp 38.1°C`
6. Click **Complete Assessment**
7. **Check:** Results show symptoms and recommendations

### Scenario C: Voice Recording (Triage)

1. Start a new triage, choose any language
2. Click the **microphone** button
3. **Say clearly:**
   > "I have chest pain and shortness of breath since this morning. I have high blood pressure."
4. Click **Stop & Process**
5. **Check:** Transcript appears, then triage results

---

## Demo 2: Scribe (Doctor Consultation → SOAP Note)

**What it does:** The doctor records the consultation. The AI transcribes it, detects Pidgin if used, and generates a SOAP note.

### Scenario A: English Consultation

1. Go to **Scribe**
2. Select a patient (or go from Patients → **New Consultation**)
3. Click the **red microphone** to start recording
4. **Say (as the doctor):**
   > "Good morning. What brings you in today?"
5. **Pause, then say (as the patient):**
   > "I have had a cough and fever for three days. My chest hurts when I cough."
6. **Say (as the doctor):**
   > "Any difficulty breathing? Are you on any medications?"
7. **Say (as the patient):**
   > "A little short of breath. I take amoxicillin from the pharmacy."
8. **Say (as the doctor):**
   > "I'll listen to your chest. Breath in and out. I hear some crackles on the right. I'm assessing right lower lobe pneumonia. We'll start you on Co-amoxiclav and paracetamol. Return in 48 hours if no improvement."
9. Click **Stop** to end recording
10. **Check:** Transcript appears with DR/PT labels; SOAP note fills in (Subjective, Objective, Assessment, Plan)

### Scenario B: Pidgin / Mixed Language

1. Select a patient, start recording
2. **Say (mix of English and Pidgin):**
   > "How far, wetin dey do you? … Body dey pain you for where? … Belle dey run you? Okay, I go give you medicine. Make you drink plenty water."
3. Click **Stop**
4. **Check:** "Pidgin Detected" badge appears; SOAP note is generated

---

## Demo 3: Patients (Longitudinal Record)

**What it does:** View a patient’s record, AI summary, and SOAP history.

1. Go to **Patients**
2. Click a patient in the left list (e.g. Tunde Bakare, Ifeoma Nnaji)
3. **Check:** Patient header, vitals, allergies
4. **Check:** AI-Summarized History (chronic conditions, flagged patterns)
5. **Check:** Consultation History (SOAP cards)
6. Use the search box to filter notes
7. Click **New Consultation** → should open Scribe with that patient

---

## Demo 4: Handover Report

**What it does:** Generate a shift handover summary for the incoming doctor.

1. Ensure you have an active shift (Dashboard → **Start shift** if needed)
2. Go to **Handover**
3. (Optional) Add notes: `All critical patients reviewed. Labs pending for Bed 4.`
4. Click **Generate Report**
5. **Check:** Critical, Stable, and Discharged sections
6. **Check:** Unit summary (patients seen, critical count)
7. Click **Print** to test print view

---

## Quick Reference: What to Say

| Feature | Example phrases to say |
|---------|------------------------|
| **Triage (patient)** | "My child has fever and cough for 2 days. Temperature 39. He's not eating." |
| **Triage (Pidgin)** | "Belle dey pain me, head dey bang me. I no fit sleep." |
| **Triage (voice)** | "I have chest pain and shortness of breath. I have high blood pressure." |
| **Scribe (doctor)** | "Good morning. What brings you in? … I'm assessing upper respiratory tract infection. I'll prescribe paracetamol and advise rest." |
| **Scribe (Pidgin)** | "Wetin dey do you? … Body dey pain you? … I go give you medicine." |

---

## Demo Order (Full Run)

1. **Login** → Dashboard  
2. **Triage** → English scenario → complete → assign to patient  
3. **Patients** → open patient → view AI summary and SOAP  
4. **Scribe** → select patient → record consultation → check SOAP  
5. **Handover** → generate report  
6. **Triage** → Pidgin scenario (optional)  
7. **Scribe** → Pidgin/mixed (optional)

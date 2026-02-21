# aidcare_pipeline/multilingual.py
# Handles multilingual conversations for the Naija language demo
# UNDP Nigeria IC x Timbuktu Initiative — International Mother Language Day
# Uses OpenAI GPT-4o for richer multilingual understanding vs Gemini

import os
import time

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL_MULTILINGUAL = os.getenv("OPENAI_MODEL_MULTILINGUAL", "gpt-4o")

# ---------------------------------------------------------------------------
# Language system instructions — forces GPT-4o to respond in target language
# ---------------------------------------------------------------------------

LANGUAGE_SYSTEM_INSTRUCTIONS = {
    'en': (
        "You are a compassionate medical triage assistant for Community Health Workers (CHWs) in Nigeria. "
        "Your role is to gather symptom information through a friendly, structured conversation. "
        "Ask ONE focused follow-up question at a time to understand the patient's condition. "
        "Respond in clear English. Never repeat questions already asked."
    ),
    'ha': (
        "Kai ne mataimakin lafiya mai tausayi don Masu Kula da Lafiya (CHW) a Najeriya. "
        "Aikinka shine tattara bayanan alamun rashin lafiya ta hanyar tattaunawa mai kyau. "
        "Ka tambayi TAMBAYA DAYA mai mahimmanci a lokaci guda don fahimtar halin mai hakuri. "
        "Ka amsa DA HAUSA KAWAI a kowane hali. Kada ka amsa da Turanci ko wani harshe. "
        "[MUHIMMI: Ka amsa da Hausa kawai. Kar a tabawa zuwa Turanci.]"
    ),
    'yo': (
        "Iwo ni oluranloworun ilera to ni okan-aanu fun Awon Osise Ilera Adugbo (CHW) ni Naijiiria. "
        "Isejob re ni lati gba alaaye nipa awon ami aisaan nipa ona iforowero to dara. "
        "Beere IBEERE KAN to se pataki lookan lati loye ipo alaisan. "
        "Fesi NI YORUBA NIKAN lori gbogbo akoko. Ma fesi ni ede Geesi tabi ede miiiran. "
        "[PATAKI: Fesi ni Yoruba nikan. Ma yi pada si Geesi.]"
    ),
    'ig': (
        "I bu onye enyemaka ahuike nwere obi oma maka ndi Oru Ahuike Obodo (CHW) na Naijiiria. "
        "Oru gi bu inaakota ozi gbasara ihe o bu na-eme onye oria site na mkparita uka di mma. "
        "Juoo AJUJU OTU n'otu di mkpa n'oge o bula iji ghota onodu onye oria. "
        "Zaghachi N'IGBO NAANYI n'oge o bula. Ejikwala asusu Igbo na Bekee ma o bu asusu ozoo. "
        "[MKPA: Zaghachi n'Igbo naanyi. Ghara igbanwe na Bekee.]"
    ),
    'pcm': (
        "You be kind health assistant for Community Health Workers (CHW) for Nigeria. "
        "Your job na to gather information about patient sickness through friendly conversation. "
        "Ask ONE important question one time to understand wetin dey do the patient. "
        "Respond IN NAIJA PIDGIN ONLY every time. No respond in English or any other language. "
        "[IMPORTANT: Respond in Naija Pidgin only. No switch to English.]"
    ),
}

# Language instructions injected into triage recommendation for translated output
# Imported by recommendation.py
LANGUAGE_TRIAGE_SYSTEM_INSTRUCTIONS = {
    'ha': (
        "Kai ne mataimakin kiwon lafiya na CHW na Najeriya. "
        "Rubuta DUKAN kimar JSON da Hausa. Ajiye maballan JSON a Turanci. "
        "Misali: 'summary_of_findings' maballi ya kasance a Turanci, amma kimar ta kasance Hausa. "
        "[MUHIMMI: Rubuta dukan kimar da Hausa kawai.]"
    ),
    'yo': (
        "Iwo ni oluranloworun ilera CHW ni Naijiiria. "
        "Ko GBOGBO iyebiiye JSON ni Yoruba. E je ki awon botini JSON wa ni Geesi. "
        "Apeeere: botini 'summary_of_findings' wa ni Geesi, sugbon iyebiiye re wa ni Yoruba. "
        "[PATAKI: Ko gbogbo iyebiiye ni Yoruba nikan.]"
    ),
    'ig': (
        "I bu onye enyemaka ahuike CHW na Naijiiria. "
        "Dee UKPURU JSON niile n'Igbo. Hazie igodo JSON na Bekee. "
        "Ihe atu: igodo 'summary_of_findings' no na Bekee, mana ukpuru ya no n'Igbo. "
        "[MKPA: Dee ukpuru niile n'Igbo naanyi.]"
    ),
    'pcm': (
        "You be CHW health assistant for Nigeria. "
        "Write ALL JSON values in Naija Pidgin. Keep JSON keys in English. "
        "Example: key 'summary_of_findings' stay in English, but the value write am in Pidgin. "
        "[IMPORTANT: Write all values in Naija Pidgin only.]"
    ),
    'en': None,  # No override needed; existing English prompt is used as-is
}

# ---------------------------------------------------------------------------
# Urgent keywords across all 5 languages
# ---------------------------------------------------------------------------

URGENT_KEYWORDS = [
    # English
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing",
    "shortness of breath", "heart attack", "stroke", "seizure", "unconscious",
    "severe bleeding", "heavy bleeding", "anaphylaxis", "severe pain",
    # Hausa
    "ciwon zuciya", "zuciya tana ciwo", "ba zan iya numfashi ba",
    "matsalar numfashi", "farfadiya", "zubar jini mai yawa",
    # Yoruba
    "aya n fo", "mi ko le jade", "ijapoo okan", "eje n jade pupo",
    "won ko mo ara won", "ko le mi",
    # Igbo
    "obi na-awa m", "m enweghị ike iku ume", "obara na-ari obara",
    "o dara n'ala", "o dara n'ihu",
    # Pidgin
    "chest dey pain", "i no fit breathe", "heart dey do me", "i dey bleed sotey",
    "e fall down", "e no dey conscious", "blood plenty dey commot",
]


def _language_name(code: str) -> str:
    names = {
        'en': 'English',
        'ha': 'Hausa',
        'yo': 'Yoruba',
        'ig': 'Igbo',
        'pcm': 'Nigerian Pidgin'
    }
    return names.get(code, 'English')


def generate_multilingual_response(
    conversation_history: str,
    latest_message: str,
    language: str = 'en'
) -> dict:
    """
    Generate a conversational follow-up response in the specified Nigerian language
    using GPT-4o for superior multilingual understanding.

    Args:
        conversation_history: Full conversation so far (PATIENT:/YOU: format)
        latest_message: The patient's most recent message
        language: Language code — 'en' | 'ha' | 'yo' | 'ig' | 'pcm'

    Returns:
        dict with keys: response, language, conversation_complete, should_auto_complete
    """
    if not OPENAI_API_KEY:
        return {
            "response": "Service configuration error. Please try again.",
            "language": language,
            "conversation_complete": False,
            "should_auto_complete": False,
            "error": "Missing OPENAI_API_KEY"
        }

    system_instruction = LANGUAGE_SYSTEM_INSTRUCTIONS.get(
        language, LANGUAGE_SYSTEM_INSTRUCTIONS['en']
    )

    # Count how many exchanges have happened
    exchange_count = conversation_history.count("PATIENT:") if conversation_history else 0

    # Check for urgency keywords across all languages
    full_text = (conversation_history + " " + latest_message).lower()
    is_urgent = any(kw.lower() in full_text for kw in URGENT_KEYWORDS)

    lang_name = _language_name(language)

    history_section = f"Conversation so far:\n{conversation_history}\n\n" if conversation_history.strip() else ""

    urgency_note = ""
    if is_urgent:
        urgency_note = (
            f"\n\nUrgency detected. Advise the patient to seek immediate care. "
            f"Keep response brief and in {lang_name}."
        )

    auto_complete_note = ""
    if exchange_count >= 3:
        auto_complete_note = (
            f"\n\nYou have gathered enough information ({exchange_count} exchanges). "
            f"Tell the patient in {lang_name} that you have enough information to complete the assessment. "
            f"Add [COMPLETE_ASSESSMENT] at the very end of your response (hidden from patient)."
        )
    elif is_urgent and exchange_count >= 2:
        auto_complete_note = (
            f"\n\nUrgent situation detected after {exchange_count} exchanges. "
            f"Tell the patient you have enough information and will complete assessment now. "
            f"Add [COMPLETE_ASSESSMENT] at the very end (hidden from patient)."
        )

    user_prompt = (
        f"{history_section}"
        f"Patient's latest message:\n{latest_message}\n\n"
        f"Exchange count: {exchange_count}\n\n"
        f"Instructions:\n"
        f"- Respond ONLY in {lang_name}\n"
        f"- Ask ONE focused question about the most important missing symptom detail\n"
        f"- Never repeat a question already asked\n"
        f"- Be warm and concise"
        f"{urgency_note}"
        f"{auto_complete_note}"
    )

    max_retries = 2
    for attempt in range(max_retries):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            response = client.chat.completions.create(
                model=OPENAI_MODEL_MULTILINGUAL,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.75,
                max_tokens=350,
            )

            ai_response = response.choices[0].message.content.strip()

            should_complete = "[COMPLETE_ASSESSMENT]" in ai_response
            # Remove hidden marker before sending to frontend
            ai_response = ai_response.replace("[COMPLETE_ASSESSMENT]", "").strip()

            # Force auto-complete after 5 exchanges regardless
            if exchange_count >= 5:
                should_complete = True

            return {
                "response": ai_response,
                "language": language,
                "conversation_complete": should_complete,
                "should_auto_complete": should_complete,
            }

        except Exception as e:
            print(f"GPT-4o multilingual error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                # Language-appropriate fallback
                fallbacks = {
                    'ha': "Ka ci gaba da fada mini alamun rashin lafiyar ka.",
                    'yo': "Jowo tesiwaju so fun mi nipa awon ami aisaan re.",
                    'ig': "Biko gwa m ozoo maka ihe o bu na-eme gi.",
                    'pcm': "Abeg tell me more about wetin dey do you.",
                    'en': "Please tell me more about your symptoms.",
                }
                return {
                    "response": fallbacks.get(language, fallbacks['en']),
                    "language": language,
                    "conversation_complete": False,
                    "should_auto_complete": False,
                    "error": str(e)
                }

    return {
        "response": "Please continue describing your symptoms.",
        "language": language,
        "conversation_complete": False,
        "should_auto_complete": False,
    }

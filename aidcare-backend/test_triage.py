#!/usr/bin/env python3
"""
Test script for AidCare Triage functionality
Tests the updated Gemini 3 models integration
"""
import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TRIAGE_TEXT_ENDPOINT = f"{BASE_URL}/triage/process_text/"

# Test cases with different scenarios
TEST_CASES = [
    {
        "name": "Child with Fever and Cough",
        "transcript": """
        Doctor: Good morning, what brings you in today?
        Mother: My 3-year-old son has been having fever for 2 days now.
        Doctor: How high is the fever?
        Mother: It goes up to 39 degrees Celsius. He also has a bad cough.
        Doctor: Is he eating well?
        Mother: Not really, he doesn't have much appetite.
        Doctor: Any difficulty breathing?
        Mother: A little bit, especially at night.
        """
    },
    {
        "name": "Adult with Chest Pain",
        "transcript": """
        Doctor: What's bothering you today?
        Patient: I've been experiencing chest pain since yesterday evening.
        Doctor: Can you describe the pain?
        Patient: It's a sharp pain on the left side, worse when I breathe deeply.
        Doctor: Any shortness of breath?
        Patient: Yes, a little bit.
        Doctor: Do you have any medical conditions?
        Patient: I have high blood pressure and I'm on medication.
        """
    },
    {
        "name": "Headache and Fatigue",
        "transcript": """
        Doctor: Hello, what seems to be the problem?
        Patient: I've had a severe headache for the past 3 days.
        Doctor: Where exactly is the headache?
        Patient: It's across my forehead and temples, very intense.
        Doctor: Any other symptoms?
        Patient: Yes, I'm extremely tired and feel weak all the time.
        Doctor: Any fever?
        Patient: Yes, I had a slight fever yesterday.
        """
    }
]

def print_separator(char="=", length=80):
    """Print a separator line"""
    print(char * length)

def print_section(title):
    """Print a section header"""
    print_separator()
    print(f" {title}")
    print_separator()

def test_health_endpoint():
    """Test if the server is running and healthy"""
    print_section("TESTING SERVER HEALTH")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("✓ Server is healthy")
            print(f"\nServer Status:")
            print(json.dumps(health_data, indent=2))
            return True
        else:
            print(f"✗ Health check failed with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Is it running?")
        print(f"  Make sure the server is running at {BASE_URL}")
        print("\n  To start the server, run:")
        print("  cd aidcare-backend")
        print("  uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"✗ Error checking health: {e}")
        return False

def test_triage_case(test_case):
    """Test a single triage case"""
    print_section(f"TEST CASE: {test_case['name']}")

    print(f"Transcript:")
    print(test_case['transcript'].strip())
    print("\n" + "-" * 80)

    payload = {
        "transcript_text": test_case['transcript']
    }

    print("\nSending request to triage endpoint...")
    start_time = time.time()

    try:
        response = requests.post(
            TRIAGE_TEXT_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60  # Gemini calls can take some time
        )

        elapsed_time = time.time() - start_time

        if response.status_code == 200:
            print(f"✓ Request successful (took {elapsed_time:.2f}s)")
            result = response.json()

            # Display results
            print("\n" + "=" * 80)
            print(" TRIAGE RESULTS")
            print("=" * 80)

            # Extracted Symptoms
            print("\n📋 EXTRACTED SYMPTOMS:")
            symptoms = result.get('extracted_symptoms', [])
            if symptoms:
                for symptom in symptoms:
                    print(f"  • {symptom}")
            else:
                print("  (No symptoms extracted)")

            # Retrieved Guidelines
            print("\n📚 RETRIEVED GUIDELINES:")
            guidelines = result.get('retrieved_guidelines_summary', [])
            if guidelines:
                for i, guide in enumerate(guidelines, 1):
                    print(f"  {i}. {guide.get('source')} - {guide.get('code')}")
                    print(f"     Case: {guide.get('case')}")
                    print(f"     Score: {guide.get('score', 'N/A')}")
            else:
                print("  (No guidelines retrieved)")

            # Triage Recommendation
            print("\n🏥 TRIAGE RECOMMENDATION:")
            recommendation = result.get('triage_recommendation', {})

            if recommendation:
                # Summary
                summary = recommendation.get('summary_of_findings', '')
                if summary:
                    print(f"\n  Summary:")
                    print(f"  {summary}")

                # Urgency Level
                urgency = recommendation.get('urgency_level', '')
                if urgency:
                    print(f"\n  ⚠️  Urgency Level: {urgency}")

                # Recommended Actions
                actions = recommendation.get('recommended_actions_for_chw', [])
                if actions:
                    print(f"\n  Recommended Actions:")
                    for action in actions:
                        print(f"  {action}")

                # Key References
                references = recommendation.get('key_guideline_references', [])
                if references:
                    print(f"\n  Guidelines Referenced:")
                    for ref in references:
                        print(f"  • {ref}")

                # Important Notes
                notes = recommendation.get('important_notes_for_chw', [])
                if notes:
                    print(f"\n  Important Notes:")
                    for note in notes:
                        print(f"  ⚠️  {note}")
            else:
                print("  (No recommendation generated)")

            print("\n" + "=" * 80)
            return True

        else:
            print(f"✗ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("✗ Request timed out. The model might be taking too long to respond.")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test runner"""
    print("\n" + "=" * 80)
    print(" AIDCARE TRIAGE TEST SUITE")
    print(" Testing Gemini 3 Models Integration")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Test server health first
    if not test_health_endpoint():
        print("\n❌ Server health check failed. Cannot proceed with tests.")
        print("\nPlease ensure:")
        print("1. The backend server is running")
        print("2. The .env file has the correct GOOGLE_API_KEY")
        print("3. The Gemini models are properly configured")
        return

    print("\n✓ Server is ready. Starting triage tests...\n")
    time.sleep(2)

    # Run test cases
    results = []
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n\n{'='*80}")
        print(f" TEST {i}/{len(TEST_CASES)}")
        print(f"{'='*80}\n")

        success = test_triage_case(test_case)
        results.append({
            "name": test_case["name"],
            "success": success
        })

        # Wait between tests to avoid rate limiting
        if i < len(TEST_CASES):
            print("\n⏳ Waiting 3 seconds before next test...")
            time.sleep(3)

    # Summary
    print("\n\n" + "=" * 80)
    print(" TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r["success"])
    total = len(results)

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")

    print("\nDetailed Results:")
    for result in results:
        status = "✓ PASSED" if result["success"] else "✗ FAILED"
        print(f"  {status} - {result['name']}")

    print("\n" + "=" * 80)

    if passed == total:
        print("🎉 All tests passed! The triage system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")

    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()

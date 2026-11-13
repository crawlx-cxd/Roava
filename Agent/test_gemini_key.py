"""
test_gemini_key.py - Gemini API Diagnostic and Connection Tester

Diagnoses Gemini API keys, queries ModelService.ListModels, tests generateContent,
and pinpoints the exact cause of any 400/403/404 errors.
"""

import os
import sys
import json
import urllib.request
import urllib.error


def diagnose_key(api_key: str):
    # Sanitize key
    clean_key = api_key.strip().strip("'\"").strip()
    if not clean_key:
        print("❌ Error: API key is empty.")
        return

    print("=" * 70)
    print("🔍 GEMINI API DIAGNOSTIC TOOL")
    print("=" * 70)
    print(f"Key Preview: {clean_key[:6]}...{clean_key[-4:]} (Length: {len(clean_key)})")

    # Step 1: Query ModelService.ListModels
    print("\n[Step 1] Querying ModelService.ListModels to check enabled models...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
    req = urllib.request.Request(list_url, headers={"User-Agent": "GeminiDiagnostic/1.0"})

    models_found = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            all_models = data.get("models", [])
            print(f"✅ Success! Google returned {len(all_models)} total models for your account.")

            def is_text_model(name: str) -> bool:
                lower = name.lower()
                banned = ["tts", "audio", "embedding", "aqa", "imagen", "image"]
                return not any(b in lower for b in banned)

            for m in all_models:
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "").replace("models/", "")
                    if is_text_model(name):
                        models_found.append(name)

            print(f"✅ Found {len(models_found)} text-generation models:")
            for name in models_found[:8]:
                print(f"   • {name}")
            if len(models_found) > 8:
                print(f"   ... and {len(models_found) - 8} more.")

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"❌ ListModels failed with HTTP {e.code}:")
        print(f"   {err_body}")

        if e.code == 400:
            print("\n💡 Reason: The API key is invalid or formatted incorrectly.")
            print("   Please generate a fresh key from: https://aistudio.google.com/app/apikey")
        elif e.code == 403:
            print("\n💡 Reason: Generative Language API is disabled or restricted in this Google Cloud project.")
            print("   Enable it at: https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com")
        elif e.code == 404:
            print("\n💡 Reason: Endpoint or API service not found.")
        return

    except Exception as e:
        print(f"❌ Network/Connection error: {e}")
        return

    if not models_found:
        print("\n❌ No standard text models supporting 'generateContent' were found for this key.")
        return

    # Step 2: Test generateContent with the best available text model
    preferences = [
        "gemini-flash-lite-latest",
        "gemini-3.8-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]
    best_model = None
    for pref in preferences:
        if pref in models_found:
            best_model = pref
            break
    if not best_model:
        best_model = models_found[0]

    print(f"\n[Step 2] Testing generateContent with selected model: '{best_model}'...")
    gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{best_model}:generateContent?key={clean_key}"
    payload = {
        "contents": [{"parts": [{"text": "Say 'Gemini connection successful' in 5 words."}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 64}
    }
    gen_req = urllib.request.Request(
        gen_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(gen_req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                reply = candidates[0]["content"]["parts"][0]["text"].strip()
                print(f"✅ SUCCESS! Response from Gemini ({best_model}):")
                print(f"   \"{reply}\"")
                print("\n🎉 Your API key and model are working 100% properly!")
            else:
                print("⚠️ Received response but no candidates were returned.")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"❌ generateContent failed with HTTP {e.code}:")
        print(f"   {err_body}")
    except Exception as e:
        print(f"❌ Error during test generation: {e}")


if __name__ == "__main__":
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and len(sys.argv) > 1:
        key = sys.argv[1].strip()

    if not key:
        print("Enter your Gemini API key below to run diagnostic:")
        try:
            key = input("API Key > ").strip()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

    diagnose_key(key)


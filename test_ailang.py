import requests
import json

# Test 1: Domain detection
print("=== Test 1: Domain Detection ===")
r1 = requests.post("http://localhost:8000/api/ailang/translate", json={
    "text": "I need emergency help",
    "source_lang": "en",
    "target_lang": "es",
    "pipeline": "default"
})
print(f"Status: {r1.status_code}")
if r1.status_code == 200:
    data = r1.json()
    print(f"Domain: {data.get('analysis', {}).get('domain')}")
    print(f"Model: {data.get('analysis', {}).get('model')}")
    print(f"Translated: {data.get('translated_text')}")
else:
    print(f"Error: {r1.text}")

# Test 2: Medical plugin drug protection
print("\n=== Test 2: Medical Plugin Drug Protection ===")
r2 = requests.post("http://localhost:8000/api/ailang/translate", json={
    "text": "Take ibuprofen for pain",
    "source_lang": "en",
    "target_lang": "es",
    "pipeline": "default"
})
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    data = r2.json()
    translated = data.get('translated_text', '')
    print(f"Translated: {translated}")
    if '[KEEP]' in translated and '[/KEEP]' in translated:
        print("✓ Drug protection markers present")
    else:
        print("✗ Drug protection markers missing")
else:
    print(f"Error: {r2.text}")

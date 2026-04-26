"""qwen-vl-max modelini test et."""
import requests
import json

url = "http://localhost:3264/api/chat/completions"

# Test 1: qwen-vl-max text
print("=" * 50)
print("Test: qwen-vl-max (text)")
try:
    resp = requests.post(url, json={
        "model": "qwen-vl-max",
        "messages": [{"role": "user", "content": "2+2 kaçtır? Sadece sayı yaz."}],
        "max_tokens": 20
    }, timeout=30)
    data = resp.json()
    if "choices" in data:
        print(f"✅ Çalışıyor: {data['choices'][0]['message']['content']}")
    else:
        print(f"❌ Hata: {json.dumps(data, ensure_ascii=False)[:200]}")
except Exception as e:
    print(f"❌ Bağlantı hatası: {e}")

# Test 2: qwen-vl-max-latest
print("\n" + "=" * 50)
print("Test: qwen-vl-max-latest (text)")
try:
    resp = requests.post(url, json={
        "model": "qwen-vl-max-latest",
        "messages": [{"role": "user", "content": "2+2 kaçtır? Sadece sayı yaz."}],
        "max_tokens": 20
    }, timeout=30)
    data = resp.json()
    if "choices" in data:
        print(f"✅ Çalışıyor: {data['choices'][0]['message']['content']}")
    else:
        print(f"❌ Hata: {json.dumps(data, ensure_ascii=False)[:200]}")
except Exception as e:
    print(f"❌ Bağlantı hatası: {e}")

# Test 3: qwen3-vl-max
print("\n" + "=" * 50)
print("Test: qwen3-vl-max (text)")
try:
    resp = requests.post(url, json={
        "model": "qwen3-vl-max",
        "messages": [{"role": "user", "content": "2+2 kaçtır? Sadece sayı yaz."}],
        "max_tokens": 20
    }, timeout=30)
    data = resp.json()
    if "choices" in data:
        print(f"✅ Çalışıyor: {data['choices'][0]['message']['content']}")
    else:
        print(f"❌ Hata: {json.dumps(data, ensure_ascii=False)[:200]}")
except Exception as e:
    print(f"❌ Bağlantı hatası: {e}")

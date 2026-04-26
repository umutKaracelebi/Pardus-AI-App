import requests
import concurrent.futures
import time

TOKEN = "$oy*7REkTge5lnL*JpG9D40a3Md4_LZIdmI8sXK8F3CX5fbazzp_8Gn1gsBy1ogROHqapzX0Ccdj0"
URL = "http://127.0.0.1:3264/api/v1/chat/completions"

def send_request(index):
    start_time = time.time()
    payload = {
        "model": "qwen-max-latest",
        "messages": [{"role": "user", "content": f"Hello! This is test message number {index}. Please reply with just the number {index}."}],
        "stream": False
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(URL, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start_time
        if response.status_code == 200:
            content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            return f"[Request {index}] SUCCESS ({elapsed:.2f}s): {content.strip()}"
        else:
            return f"[Request {index}] FAILED ({elapsed:.2f}s): HTTP {response.status_code} - {response.text}"
    except Exception as e:
        elapsed = time.time() - start_time
        return f"[Request {index}] ERROR ({elapsed:.2f}s): {str(e)}"

if __name__ == "__main__":
    print("Starting stress test: Sending 10 concurrent requests...\n")
    start_total = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_request, i) for i in range(1, 11)]
        
        for future in concurrent.futures.as_completed(futures):
            print(future.result())
            
    print(f"\nStress test completed in {time.time() - start_total:.2f} seconds.")

import base64
from g4f.client import Client
import time

def test_model(model_name):
    client = Client()
    image_path = "images.jpeg"
    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode()
        
    data_url = f"data:image/jpeg;base64,{img_data}"
    
    print(f"Testing {model_name}...")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Bu resimde ne var? Kısa Türkçe cevap."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }],
        )
        print(f"[{model_name}] Success: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"[{model_name}] Error: {str(e)[:100]}")
        return False

if __name__ == "__main__":
    for model in ["gpt-4o", "gemini-1.5-pro", "claude-3.5-sonnet", "llava"]:
        success = test_model(model)
        if success:
            break
        time.sleep(2)

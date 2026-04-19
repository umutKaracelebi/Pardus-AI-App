import base64
from g4f.client import Client
from g4f.Provider import DeepInfra

def test():
    client = Client(provider=DeepInfra)
    model_name = "moonshotai/Kimi-K2.5"
    
    print(f"Testing {model_name} Chat...")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Merhaba Kimi, nasılsın?"}],
        )
        print("Chat Success:", response.choices[0].message.content)
    except Exception as e:
        print("Chat Error:", e)

    print(f"\nTesting {model_name} Vision...")
    image_path = "images.jpeg"
    try:
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
            
        data_url = f"data:image/jpeg;base64,{img_data}"
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Bu resimde ne var?"},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }],
        )
        print("Vision Success:", response.choices[0].message.content)
    except Exception as e:
        print("Vision Error:", e)

if __name__ == "__main__":
    test()

import base64
from g4f.client import Client
from g4f.Provider import DeepInfra

def test_vision():
    client = Client(provider=DeepInfra)
    
    # Try with a small local image
    image_path = "images.jpeg"
    try:
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
            
        data_url = f"data:image/jpeg;base64,{img_data}"
        
        # Test GLM-5.1 with vision
        response = client.chat.completions.create(
            model="zai-org/GLM-5.1",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Bu resimde ne var? Türkçe açıkla."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }],
        )
        print("GLM-5.1 Vision Success:", response.choices[0].message.content)
    except Exception as e:
        print("GLM-5.1 Vision Error:", e)

    # Test an alternative vision model like Llama 3.2 Vision on DeepInfra if GLM fails
    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Bu resimde ne var? Türkçe açıkla."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }],
        )
        print("Llama Vision Success:", response.choices[0].message.content)
    except Exception as e:
        print("Llama Vision Error:", e)

if __name__ == "__main__":
    test_vision()

from g4f.client import Client
from g4f.Provider import DeepInfra

client = Client(provider=DeepInfra)
try:
    response = client.chat.completions.create(
        model="zai-org/GLM-5.1",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print("Success:", response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")

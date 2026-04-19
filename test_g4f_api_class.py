from src.core.g4f_api import G4FAPI

def test_api():
    api = G4FAPI()
    
    print("Testing generate_response...")
    try:
        res = api.generate_response([{"role": "user", "content": "Merhaba!"}])
        print(f"Chat response: {res}")
    except Exception as e:
        print(f"Chat error: {e}")
        
    print("\nTesting generate_vision_response...")
    try:
        res = api.generate_vision_response("Bu resimde ne var?", "images.jpeg")
        print(f"Vision response: {res}")
    except Exception as e:
        print(f"Vision error: {e}")

if __name__ == "__main__":
    test_api()

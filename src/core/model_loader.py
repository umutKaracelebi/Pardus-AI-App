import os
import sys
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

class ModelLoader:
    def __init__(self, model_path="ai_files"):
        self.model_path = os.path.abspath(model_path)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.processor = None

    def load_model(self):
        print(f"Qwen2-VL-2B-Instruct yükleniyor... Cihaz: {self.device}")
        
        try:
            # Model yükleme
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_path,
                torch_dtype="auto",
                device_map="auto" if self.device == "cuda" else None
            )
            
            if self.device == "cpu":
                self.model = self.model.to("cpu")

            # Processor yükleme
            self.processor = AutoProcessor.from_pretrained(self.model_path)
            
            print("✓ Model ve Processor başarıyla yüklendi!")
            return self.model, self.processor

        except Exception as e:
            print(f"✗ HATA: Model yüklenirken bir sorun oluştu:")
            print(f"  {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None

    def generate_response(self, prompt, max_new_tokens=512):
        """Generate a text response from the local model."""
        if self.model is None or self.processor is None:
            self.load_model()
        
        if self.model is None or self.processor is None:
            raise RuntimeError("Yerel model yüklenemedi. Lütfen model dosyalarının 'ai_files' klasöründe olduğundan emin olun.")

        messages = [
            {"role": "system", "content": "Sen yardımcı bir Türkçe yapay zeka asistanısın."},
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(text=[text], return_tensors="pt").to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
        
        # Decode only the new tokens
        generated_ids_trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
        output_text = self.processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True)[0]
        return output_text


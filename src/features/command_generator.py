import json

class CommandGenerator:
    def __init__(self, model_loader):
        self.model = model_loader.model
        self.processor = model_loader.processor
        self.device = model_loader.device

    def generate_command(self, user_query):
        """Generates a Linux shell command based on the user's natural language query."""
        
        system_prompt = (
            "You are a helpful assistant that translates natural language descriptions into Linux shell commands. "
            "Output ONLY the shell command, without any explanation, markdown formatting, or code blocks. "
            "If the request is unsafe or unclear, output 'UNSAFE' or 'UNCLEAR'.\n"
            "Example: 'List all text files' -> 'find . -name \"*.txt\"'\n"
            "Example: 'Show me disk usage' -> 'df -h'"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{system_prompt}\n\nQuery: {user_query}"}
                ]
            }
        ]

        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        
        inputs = self.processor(
            text=[text],
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self.device)

        generated_ids = self.model.generate(**inputs, max_new_tokens=64)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        return output_text.strip()

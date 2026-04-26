import requests
import os
import time
import uuid

TOKEN = "$oy*7REkTge5lnL*JpG9D40a3Md4_LZIdmI8sXK8F3CX5fbazzp_8Gn1gsBy1ogROHqapzX0Ccdj0"
UPLOAD_URL = "http://127.0.0.1:3264/api/files/upload"
CHAT_URL = "http://127.0.0.1:3264/api/v1/chat/completions"

def test_doc_upload(filepath, question):
    print(f"\n--- Testing {filepath} ---")
    mime_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    }
    ext = os.path.splitext(filepath)[1].lower()
    mime_type = mime_types.get(ext, "application/octet-stream")

    with open(filepath, "rb") as f:
        files = {"file": (os.path.basename(filepath), f, mime_type)}
        headers = {"Authorization": f"Bearer {TOKEN}"}
        response = requests.post(UPLOAD_URL, files=files, headers=headers)
        if response.status_code != 200:
            print(f"Upload failed: {response.text}")
            return
        res_json = response.json()
        if not res_json.get("success"):
            print(f"Upload failed: {res_json}")
            return
        
        file_info = res_json["file"]
        print(f"Uploaded successfully. File ID: {file_info.get('file_id')}")
        
        current_time = int(time.time() * 1000)
        user_id = file_info.get("file_path").split("/")[0] if file_info.get("file_path") else ""
        item_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        qwen_file = {
            "type": "file",
            "file": {
                "created_at": current_time,
                "data": {},
                "filename": file_info.get("name"),
                "hash": None,
                "id": file_info.get("file_id"),
                "meta": {
                    "name": file_info.get("name"),
                    "size": file_info.get("size"),
                    "content_type": file_info.get("type")
                },
                "name": file_info.get("name"),
                "parse_meta": {"parse_status": "success"},
                "parse_status": "success",
                "size": file_info.get("size"),
                "update_at": current_time,
                "user_id": user_id
            },
            "file_class": "document",
            "file_type": file_info.get("type"),
            "greenNet": "success",
            "id": file_info.get("file_id"),
            "itemId": item_id,
            "name": file_info.get("name"),
            "progress": 0,
            "showType": "file",
            "size": file_info.get("size"),
            "status": "uploaded",
            "uploadTaskId": task_id,
            "url": file_info.get("url")
        }

        payload = {
            "model": "qwen3.5-plus",
            "messages": [
                {
                    "role": "user",
                    "content": question,
                    "files": [qwen_file]
                }
            ],
            "stream": False
        }

        print("Sending chat request...")
        chat_res = requests.post(CHAT_URL, json=payload, headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        if chat_res.status_code == 200:
            print("Response:\n", chat_res.json()['choices'][0]['message']['content'])
        else:
            print("Chat error:", chat_res.status_code, chat_res.text)

if __name__ == "__main__":
    files_to_test = ["test.docx", "Excel-Test.xlsx", "test.pptx"]
    for f in files_to_test:
        test_doc_upload(f, "Bu belgenin içeriği ne hakkında? Kısaca özetler misin?")

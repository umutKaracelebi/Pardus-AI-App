import requests
import json
import uuid
import time

token = open('/home/umut/qwen_free/session/accounts/acc_1776549620459/token.txt').read().strip()

def get_sts():
    url = 'https://chat.qwen.ai/api/v2/files/getstsToken'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "filename": "test.pdf",
        "filesize": 13264,
        "filetype": "document"
    }
    res = requests.post(url, headers=headers, json=payload)
    return res.json()

sts = get_sts()
print("STS:", sts)

file_id = sts['data']['file_id']
file_url = sts['data']['file_url']
file_path = sts['data']['file_path']
user_id = file_path.split('/')[0]

# Upload to OSS
with open('/home/umut/qwen_free/test.pdf', 'rb') as f:
    oss_res = requests.put(file_url, data=f, headers={'Content-Type': 'application/pdf'})
print("OSS Upload:", oss_res.status_code)

# Send Chat
chat_url = 'https://chat.qwen.ai/api/v2/chat/completions'
chat_id = str(uuid.uuid4())
message_id = str(uuid.uuid4())
child_id = str(uuid.uuid4())
current_time = int(time.time() * 1000)

chat_payload = {
    "stream": False,
    "version": "2.1",
    "incremental_output": True,
    "chat_id": chat_id,
    "chat_mode": "normal",
    "model": "qwen-max-latest",
    "parent_id": None,
    "messages": [{
        "fid": message_id,
        "parentId": None,
        "childrenIds": [child_id],
        "role": "user",
        "content": "What is this file?",
        "user_action": "chat",
        "files": [{
            "type": "file",
            "file": {
                "created_at": current_time,
                "data": {},
                "filename": "test.pdf",
                "hash": None,
                "id": file_id,
                "meta": {
                    "name": "test.pdf",
                    "size": 13264,
                    "content_type": "application/pdf"
                },
                "name": "test.pdf",
                "parse_meta": {"parse_status": "success"},
                "parse_status": "success",
                "size": 13264,
                "update_at": current_time,
                "user_id": user_id
            },
            "file_class": "document",
            "file_type": "application/pdf",
            "greenNet": "success",
            "id": file_id,
            "itemId": str(uuid.uuid4()),
            "name": "test.pdf",
            "progress": 0,
            "showType": "file",
            "size": 13264,
            "status": "uploaded",
            "uploadTaskId": str(uuid.uuid4()),
            "url": file_url
        }],
        "timestamp": int(current_time / 1000),
        "models": ["qwen-max-latest"],
        "chat_type": "t2t",
        "feature_config": {
            "thinking_enabled": False,
            "output_schema": "phase"
        },
        "extra": {"meta": {"subChatType": "t2t"}},
        "sub_chat_type": "t2t",
        "parent_id": None
    }],
    "timestamp": int(current_time / 1000)
}

chat_headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}
chat_res = requests.post(chat_url, headers=chat_headers, json=chat_payload)
print("CHAT RESPONSE:", chat_res.text)

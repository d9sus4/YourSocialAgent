from flask import *
from api import *
from llm import ask_chatgpt
import json
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor

tenant_token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
def reply_url(message_id):
    return f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
app_id = "cli_a4873d8eea79500e"
app_secret = "IudeMnAsLZkuuXhHmhFRecWssK6Rq3i2"

access_token = ""

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, World!"

# @app.route('/api/message', methods=['POST'])
# def new_message():
#     abort = not flask.request.json \
#         or not 'person' in flask.request.json \
#         or not 'type' in flask.request.json \
#         or not 'text' in flask.request.json
#     if abort:
#         flask.abort(400)
#     task = {
#         'id': tasks[-1]['id'] + 1,
#         'title': request.json['title'],
#         'description': request.json.get('description', ""),
#         'done': False
#     }
#     tasks.append(task)
#     return flask.jsonify({'task': task}), 201

@app.route('/chatbot_webhook', methods=['post'])
def webhook():
    if not request.json:
        abort(400)
    if "challenge" in request.json:
        response = {"challenge": request.json["challenge"]}
        return jsonify(response)
    elif request.json.get("schema", "") == "2.0":
        header = request.json.get("header", {})
        event_type = header.get("event_type", "")
        event = request.json.get("event", {})
        if event_type == "im.message.receive_v1": # receive a message from user
            message = event.get("message", {})
            message_id = message.get("message_id", None)
            message_type = message.get("message_type", "")
            content = message.get("content", r"{}")
            content = json.loads(content)
            if message_type == "text": # receive a text
                text = content.get("text", "")
                if len(text) > 0:
                    t = threading.Thread(target=ask_chatgpt_and_reply, args=(text, message_id))
                    t.start()
        return "", 200

def ask_chatgpt_and_reply(text, message_id):
    res = ask_chatgpt(text)
    reply(res, message_id)
    
def reply(text, message_id):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    post_data = {
        "content": json.dumps({"text": text}),
        "msg_type": "text"
    }
    retry = 0
    while retry <= 5:
        r = requests.post(reply_url(message_id), data=post_data, headers=headers)
        try:
            code = r.json()["code"]
        except ValueError:
            code = 0
        if code == 0:
            return
        retry += 1
    print("Reply message failed!")
    

def fetch_feishu_access_token():
    global access_token
    post_data = {"app_id": app_id, "app_secret": app_secret}
    retry = 0
    while retry <= 5:
        r = requests.post(tenant_token_url, data=post_data)
        try:
            code = r.json()["code"]
        except ValueError:
            code = 0
        if code == 0:
            access_token = r.json()["tenant_access_token"]
            print(f"New access token fetched: {access_token}")
            expire = int(r.json()["expire"]) # seconds
            t = threading.Timer(expire, fetch_feishu_access_token)
            t.start()
            return
        retry += 1
    print("Fetch access token failed! Retry after 1 min.")
    t = threading.Timer(60, fetch_feishu_access_token)
    t.start()


if __name__ == '__main__':
    print("Initializing...")
    fetch_feishu_access_token() # will be scheduled according to expire time
    app.run(host="0.0.0.0", port="5000")
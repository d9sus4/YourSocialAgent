from flask import *
from api import *
from llm import ask_chatgpt
import json
import requests
from pathlib import Path
import time
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

print("Initializing...")

# api & tokens
tenant_token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
def reply_url(message_id):
    return f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
app_id = "cli_a4873d8eea79500e"
app_secret = "IudeMnAsLZkuuXhHmhFRecWssK6Rq3i2"
open_id = "ou_f0aa230a1e9323d07f76a9a9a727c561"
access_token = ""

# chat meta info
chats = {}
# save chat meta info before exit
def exit_handler(signum, frame):
    try:
        with open(filename, 'w', encoding="utf8") as f:
            json.dump(chats, f, ensure_ascii=False)
    except EnvironmentError:
        raise DBError("Dumping json failed!")
    exit()
# load chat group meta
filename = str(Path("./data") / "chat.json")
if os.path.exists(filename):
    try:
        with open(filename, 'r', encoding="utf8") as f:
            chats = json.load(f)
    except EnvironmentError:
        raise DBError("Loading json failed!")
signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGTERM, exit_handler)
signal.signal(signal.SIGABRT, exit_handler)

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

@app.route('/event', methods=['post'])
def webhook():
    if not request.json:
        abort(400)
    if "challenge" in request.json: # webhook verification
        response = {"challenge": request.json["challenge"]}
        return jsonify(response)
    elif request.json.get("schema", "") == "2.0":
        header = request.json.get("header", {})
        event_type = header.get("event_type", "")
        event = request.json.get("event", {})
        if event_type == "im.message.receive_v1": # receive event
            message = event.get("message", {})
            message_id = message.get("message_id", None)
            message_type = message.get("message_type", "")
            chat_id = message.get("chat_id", None)
            chat_type = message.get("chat_type", "")
            content = message.get("content", r"{}")
            content = json.loads(content)
            mentions = message.get("mentions", None)
            sender = event.get("sender", {})
            sender_id = sender.get("sender_id", {})
            sender_open_id = sender_id.get("open_id", "")
            if chat_type == "p2p": # receive from p2p user, act as a chatbot
                if message_type == "text":
                    text = content.get("text", "")
                    if len(text) > 0:
                        t = threading.Thread(target=ask_chatgpt_and_reply, args=(text, message_id))
                        t.start()
            elif chat_type == "group": # receive from a group, act as a chat helper
                # ensure chat_id is received
                if chat_id is None:
                    print("Message from unknown chat group, ignored.")
                    abort(400)
                if chat_id not in chats.keys():
                    chats[chat_id] = {
                        "main_user": "UNDEFINED",
                        "chat_with": "UNDEFINED"
                        }
                main_user = chats[chat_id]["main_user"]
                chat_with = chats[chat_id]["chat_with"]
                print(f"New group message incoming, main: {main_user}, with: {chat_with}")
                if mentions is not None and len(mentions) == 1 and mentions[0].get("id", {}).get("open_id", "") == open_id: # @ robot, must be command
                    if message_type == "text":
                        text = content.get("text", "")
                        text = text.replace("@_user_1", "").strip()
                        slots = text.split(' ', 1)
                        print(slots)
                        if len(slots) > 0:
                            if slots[0] == "/main":
                                chats[chat_id]["main_user"] = sender_open_id
                                print(f"Main user set to {sender_open_id}.")
                                t = threading.Thread(target=ack, args=(message_id, ))
                                t.start()
                            elif slots[0] == "/person" and len(slots) > 1:
                                chats[chat_id]["chat_with"] = slots[1].strip()
                                print(f"Chatting with {slots[1].strip()}.")
                                t = threading.Thread(target=ack, args=(message_id, ))
                                t.start()
                            elif slots[0] == "/prompt" and len(slots) > 1:
                                prompt = slots[1].strip()
                                new_prompt(chat_with, prompt)
                                print(f"New prompt \"{prompt}\" has been added to {chat_with}.")
                                t = threading.Thread(target=ack, args=(message_id, ))
                                t.start()
                            elif slots[0] == "/clearprompt":
                                clear_prompt(person=chat_with)
                                print(f"Prompt of {chat_with} cleared.")
                                t = threading.Thread(target=ack, args=(message_id, ))
                                t.start()
                            elif slots[0] == "/clearchatlog":
                                clear_chatlog(person=chat_with)
                                print(f"Chat log with {chat_with} cleared.")
                                t = threading.Thread(target=ack, args=(message_id, ))
                                t.start()
                            elif slots[0] == "/suggest":
                                keywords = slots[1:]
                                t = threading.Thread(target=suggest_and_reply, args=(chat_with, "chatgpt", 3, keywords, message_id))
                                t.start()
                else: # regular message, record them
                    if message_type == "text":
                        text = content.get("text", "")
                        new_message(person=chat_with, text=text, send=sender_open_id == main_user)
                        print(f"New message recorded. Sender id: {sender_open_id}.")
        return "", 200

def ask_chatgpt_and_reply(text, message_id):
    res = ask_chatgpt(text)
    reply(res, message_id)

def suggest_and_reply(person: str, model: str, n_replies: int, keywords: list, message_id: str):
    res = suggest_reply(person=person, model=model, n_replies=n_replies, keywords=keywords)
    text = "LLM suggests:\n"
    for i in range(len(res)):
        text += str(i+1) + ". " + res[i] + '\n'
    print(text)
    reply(text, message_id)

def ack(message_id):
    reply("Ack", message_id)

    
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
    fetch_feishu_access_token() # will be scheduled according to expire time
    app.run(host="0.0.0.0", port="5000")
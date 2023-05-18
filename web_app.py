from flask import *
from api import *
from llm import GPTSession, GPTSessionManager
import json
import requests
from pathlib import Path
import time
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

print("Initializing...")

# default macros
DEFAUT_NUM_SUGGESTION = 3

# api & tokens
tenant_token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
def reply_url(message_id):
    return f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
def send_url(receive_id_type):
    '''receive_id_type in ["chat_id",]'''
    return f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
app_id = "cli_a4873d8eea79500e"
app_secret = "IudeMnAsLZkuuXhHmhFRecWssK6Rq3i2"
open_id = "ou_f0aa230a1e9323d07f76a9a9a727c561"
access_token = ""

# chat config info, maps group ids to user-contact pairs
chats = {}
# save chat config info before exit
filename = str(Path("./data") / "config.json")
def exit_handler(signum, frame):
    try:
        with open(filename, 'w', encoding="utf8") as f:
            json.dump(chats, f, ensure_ascii=False)
    except EnvironmentError:
        raise DBError("Dumping json failed!")
    exit()
# load chat group config
if os.path.exists(filename):
    try:
        with open(filename, 'r', encoding="utf8") as f:
            chats = json.load(f)
    except EnvironmentError:
        raise DBError("Loading json failed!")
signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGTERM, exit_handler)
signal.signal(signal.SIGABRT, exit_handler)

# random chat GPT sessions
random_chat_session_manager = GPTSessionManager(default_role="a chatbot")

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
            message = event.get("message", {} )
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
                        if text[0] == '/': # command
                            print(f"New command incoming from {sender_open_id}: {text}")
                            command = text.split(' ', 1)
                            if command[0] == "/cat": # enable cat girl mode
                                session = random_chat_session_manager.get(sender_open_id)
                                if command[1] in ("1", "enable"):
                                    print(f"Enabling cat mode for {sender_open_id}.")
                                    session.configure("cat")
                                    t = threading.Thread(target=reply, args=("Cat mode enabled, MEOW!", message_id))
                                    t.start()
                                elif command[1] in ("0", "disable"):
                                    print(f"Disabling cat mode for {sender_open_id}.")
                                    session.deconfigure("cat")
                                    t = threading.Thread(target=reply, args=("Cat mode disabled. zzz...", message_id))
                                    t.start()
                                random_chat_session_manager.writeback(session)
                        else: # regular query
                            print(f"Received p2p message from {sender_open_id}: {text}")
                            t = threading.Thread(target=random_chat_query, args=(text, sender_open_id, message_id))
                            t.start()
            elif chat_type == "group": # receive from a group, act as a chat helper
                # ensure chat_id is received
                if chat_id is None:
                    print("Message from unrecognizable chat group, ignored.")
                    abort(400)
                if chat_id not in chats.keys(): # new chat group that has no config, init new one
                    chats[chat_id] = {
                        "main_user": "UNDEFINED",
                        "chat_with": "UNDEFINED",
                        # following are added later, better use dict.get(key, default_value) when accessing cuz they possibly do not exist for earlier chats
                        "last_suggest": [],
                        "wait_for_pick": False, # valid last suggestion flag
                        "num_suggest": DEFAUT_NUM_SUGGESTION,
                        "auto_suggest": False, # if True, every new incoming msg from contact will trigger a suggestion
                        }
                # fetch meta data, as every chat group involve 3 roles: main user, contact, and the agent itself
                main_user = chats[chat_id]["main_user"]
                chat_with = chats[chat_id]["chat_with"]
                # with main user and contact name defined, DBs are able to locate
                switch_user(main_user)
                print(f"New group message incoming, main: {main_user}, contact: {chat_with}")
                if mentions is not None and len(mentions) == 1 and mentions[0].get("id", {}).get("open_id", "") == open_id: # @ robot, must be command
                    if message_type == "text":
                        text = content.get("text", "")
                        text = text.replace("@_user_1", "").strip()
                        print(f"New command incoming from {sender_open_id}: {text}")
                        command = text.split(' ', 1)
                        if len(command) > 0:
                            if command[0] == "/main": # set main user as the sender
                                chats[chat_id]["main_user"] = sender_open_id
                                print(f"Main user set to {sender_open_id}.")
                                t = threading.Thread(target=reply, args=(f"Main user of current chat session set to {sender_open_id}.", message_id))
                                t.start()
                            elif command[0] == "/contact" and len(command) > 1: # set the name of the contact
                                contact_name = command[1].strip()
                                chats[chat_id]["chat_with"] = contact_name
                                print(f"{main_user} is chatting with {contact_name}.")
                                t = threading.Thread(target=reply, args=(f"Contact name of current chat session set to {contact_name}.", message_id))
                                t.start()
                            elif command[0] == "/prompt" and len(command) > 1: # add a prompt to the contact
                                prompt = command[1].strip()
                                new_prompt(chat_with, prompt)
                                print(f"{main_user} added new prompt \"{prompt}\" to {chat_with}.")
                                t = threading.Thread(target=reply, args=(f"New prompt: {prompt} added to {chat_with}.", message_id))
                                t.start()
                            elif command[0] == "/feedback" and len(command) > 1: # feedback
                                feedback_msg = command[1].strip()
                                print(f"Received a feedback from {main_user}: {feedback_msg}, parsing...")
                                t = threading.Thread(target=feedback_query, args=(feedback_msg, "contact", chat_with, message_id)) # only contact scope by far
                                t.start()
                            elif command[0] == "/pick" and len(command) > 1: # record a pick from the latest suggestion, abandon if pick = 0
                                if not chats[chat_id]["wait_for_pick"]:
                                    print(f"{main_user} issued a pick but there is nothing to pick from!")
                                    t = threading.Thread(target=reply, args=("Nothing to pick from!", message_id))
                                    t.start()
                                else:
                                    try:
                                        pick = int(command[1].strip())
                                        if pick == 0: # pick none
                                            print(f"{main_user} picked none of the suggestions!")
                                            t = threading.Thread(target=reply, args=(f"Sorry to hear that!", message_id))
                                            t.start()
                                        else: # pick a valid one, add the message to chat log as if it was sent by main user
                                            msg = chats[chat_id]["last_suggest"][pick-1]
                                            print(f"{main_user} picked suggestion number {pick}, contents: {msg}")
                                            new_message(person=chat_with, text=msg, send=sender_open_id == main_user)
                                            print(f"New message recorded. Sender id: {sender_open_id}.")
                                            t = threading.Thread(target=reply, args=(f"Pick done & message sent!\nYou: {msg}", message_id))
                                            t.start()
                                        chats[chat_id]["wait_for_pick"] = False # reset flag
                                        print(f"Session {chat_id}'s wait for pick flag has been reset.")
                                    except (ValueError, IndexError):
                                        print(f"{main_user} issued an illegal pick!")
                                        t = threading.Thread(target=reply, args=("Illegal!", message_id))
                                        t.start()
                            elif command[0] == "/clearprompt": # clear all prompts of current contact
                                clear_prompt(person=chat_with)
                                print(f"{main_user} cleared all prompt of {chat_with}.")
                                t = threading.Thread(target=reply, args=(f"All prompt of current chat session cleared!", message_id))
                                t.start()
                            elif command[0] == "/clearchatlog": # clear all chat logs of current contact
                                clear_chatlog(person=chat_with)
                                print(f"{main_user} cleared all chat log with {chat_with}.")
                                t = threading.Thread(target=reply, args=("All log of current chat session cleared!", message_id))
                                t.start()
                            elif command[0] == "/suggest": # suggest reply thru LLM
                                hint = command[1] if len(command) > 1 else ""
                                print(f"Suggesting message for {main_user} chatting with {chat_with}, hint: {hint}.")
                                t = threading.Thread(target=suggest_query, args=(chat_with, "chatgpt", chats[chat_id].get("num_suggest", DEFAUT_NUM_SUGGESTION), hint, message_id, chat_id))
                                t.start()
                            elif command[0] == "/autosuggest": # config auto suggest
                                op = command[1].lower().strip()
                                if op == "enable":
                                    chats[chat_id]["auto_suggest"] = True
                                elif op == "disable":
                                    chats[chat_id]["auto_suggest"] = False
                                print(f"{main_user} has set auto suggest {op} chatting with {chat_with}.")
                                t = threading.Thread(target=reply, args=(f"Auto suggest {op}d!", message_id))
                                t.start()
                            elif command[0] == "/numsuggest": # config auto suggest
                                try:
                                    num = int(command[1].lower().strip())
                                    chats[chat_id]["num_suggest"] = num
                                    print(f"{main_user} has set num suggest to {num} chatting with {chat_with}.")
                                    t = threading.Thread(target=reply, args=(f"Num suggest set to {num}.", message_id))
                                    t.start()
                                except ValueError:
                                    print(f"{main_user} issued an illegal num suggest config!")
                                    t = threading.Thread(target=reply, args=("Illegal!", message_id))
                                    t.start()
                            else:
                                print(f"{main_user} issued an unknown command: {text}")
                                t = threading.Thread(target=reply, args=("Unknown command.", message_id))
                                t.start()
                else: # regular message, record them
                    if message_type == "text":
                        text = content.get("text", "")
                        new_message(person=chat_with, text=text, send=sender_open_id == main_user)
                        print(f"New message recorded. Sender id: {sender_open_id}.")
                        if sender_open_id == main_user: # reset wait for pick flag if main user send a msg
                            chats[chat_id]["wait_for_pick"] = False
                            print(f"Session {chat_id}'s wait for pick flag has been reset.")
                        else: # trigger auto suggestion (if enabled) if contact send a msg
                            if chats[chat_id].get("auto_suggest", False):
                                print(f"Auto suggesting message for {main_user} chatting with {chat_with}, no hint.")
                                t = threading.Thread(target=suggest_query, args=(chat_with, "chatgpt", chats[chat_id].get("num_suggest", DEFAUT_NUM_SUGGESTION), "", None, chat_id))
                                t.start()
        return "", 200


def random_chat_query(text, sender, message_id):
    '''For random chat only.'''
    session = random_chat_session_manager.get(sender)
    res = session.ask(text)

    # configured attributes
    if "cat" in session.attr:
        prompt = "You are a cute and lively girl cosplaying a cat.\n"
        prompt += 'You will act cutely by adding a "meow" word to the end of every sentence you say.\n'
        prompt += "Here are some examples:\n"
        prompt += "Original text: 您好，我是一名聊天机器人，专门编程来与人类进行交流和交互。我可以回答各种问题，提供有用的信息，或者只是听您发牢骚。请问有什么我可以帮助您的吗？\n"
        prompt += "Stylized text: 您好喵～我是您可爱的猫娘，专门被派来与您进行互动喵！回答您的问题、提供有用的信息，或者只是听您发牢骚都是可以的喵～请问有什么我可以帮助您的喵？\n"
        prompt += "Original text: "
        prompt += res
        prompt += "\nStylized text:"
        temp_session = GPTSession()
        res = temp_session.ask(prompt)

    print(f"ChatGPT replies: {res}")
    reply(res, message_id)
    random_chat_session_manager.writeback(session)


def suggest_query(person: str, model: str, n_replies: int, hint: str, message_id: str, chat_id: str):
    '''Suggest and reply a suggest issue.
    Hint must be str, set it empty if no hint is provided
    If message_id is None, this will not reply a certain msg, just send back to chat'''
    keywords = []
    intention = None
    if len(hint) > 0:
        hint_type = infer_hint_type(read_chatlog(person, 5), hint)
        if hint_type == "keyword":
            keywords = hint.strip().split()
            intention = None
        else:
            keywords = []
            intention = hint
    res = suggest_replies(person, model, n_replies, keywords=keywords, intention=intention)
    global chats
    chats[chat_id]["last_suggest"] = res
    chats[chat_id]["wait_for_pick"] = True
    text = "LLM suggests:\n"
    for i in range(len(res)):
        text += str(i+1) + ". " + res[i] + '\n'
    print(text)
    if message_id is not None: # reply
        reply(text, message_id)
    else: # send
        send(text, receive_id_type="chat_id", receive_id=chat_id)


def feedback_query(feedback_msg, scope, id, message_id):
    pv = param_manager.get(scope, id)
    commands = feedback2commands(feedback_msg, pv.get_all_param_names())
    update_param_by_commands(scope, id, commands)
    commands_plain = '\n'.join(commands)
    print(f"Following commands have been applied to param vector ({pv.scope}, {pv.id}):\n{commands_plain}")
    reply("Feedback has been learnt.", message_id)


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
    print("Reply Feishu message failed!")


def send(text, receive_id_type:str, receive_id:str):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    post_data = {
        "receive_id": receive_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    }
    retry = 0
    while retry <= 5:
        r = requests.post(send_url(receive_id_type), data=post_data, headers=headers)
        try:
            code = r.json()["code"]
        except ValueError:
            code = 0
        if code == 0:
            return
        retry += 1
    print("Send Feishu message failed!")


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
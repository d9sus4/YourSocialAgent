import os
import openai
from chatgpt_wrapper import ChatGPT
from revChatGPT.V1 import Chatbot
from pathlib import Path
import pickle
from error import *

# openai.api_key = "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" # mine
openai.api_key = "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" # prnake
config={"email": "prnake@gmail.com", "password": ",ejhpQc%Q4+&$9T"}

CHATGPT_API = ["chatgpt_wrapper", "rev_chatgpt", "OpenAI"][2]


def davinci_complete(prompt, temp=0.9, max_tokens=500, top_p=1, stop=["I:", "They:"], retry=5):
    res = []
    fail_cnt = 0
    while True:
        try:
            response = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                temperature=temp,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=0,
                presence_penalty=0.6,
                stop=stop
            )
            break
        except Exception:
            fail_cnt += 1
            if fail_cnt > retry:
                print("OpenAI API down!")
                return res
            print(f"Failed to access OpenAI API, count={fail_cnt}. Retrying...")
    for choice in response["choices"]:
        res.append(choice["text"].strip())
    return res

if CHATGPT_API == "chatgpt_wrapper":
    chatgpt_wrapper = ChatGPT()
    def ask_chatgpt(prompt):
        res = chatgpt_wrapper.ask(prompt)
        return res

elif CHATGPT_API == "rev_chatgpt":
    rev_chatgpt = Chatbot(config=config)
    def ask_chatgpt(prompt):
        for data in rev_chatgpt.ask(prompt): # generator
            res = data["message"]
        return res

elif CHATGPT_API == "OpenAI": # No history context. If you use ChatGPT as a continuous session, better use GPTSession below.
    def ask_chatgpt(prompt, retry=5):
        messages = [
                {"role": "system", "content": "You are a helpful assistant."},
            ]
        messages.append({"role": "user", "content": prompt})
        fail_cnt = 0
        while True:
            try:
                res = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                )["choices"][0]["message"]
                break
            except Exception:
                fail_cnt += 1
                if fail_cnt > retry:
                    print("OpenAI API down!") 
                    return "Failed to reach ChatGPT!"
                print(f"Failed to access OpenAI API, count={fail_cnt}. Retrying...")
        return res["content"]

else:
    raise NotImplementedError()

class GPTSession:
    def __init__(self, id="default", limit=100, role="a helpful assistant"):
        '''limit: how many messages between user and GPT will be recorded.'''
        self.messages = [
                {"role": "system", "content": f"You are {role}."},
            ]
        self.id = id
        self.limit = limit
        self.attr = set() # configured attributes

    def configure(self, name: str):
        self.attr.add(name)

    def deconfigure(self, name: str):
        self.attr.discard(name)
    
    def set_message_limit(self, limit: int):
        self.limit = limit

    def set_role(self, role: str):
        '''Set ChatGPT's role as {role}. This will clear chat history.'''
        self.clear_history()
        self.messages[0]["content"] = f"You are {role}."

    def clear_history(self):
        self.messages = self.messages[:1]

    def _truncate_history(self):
        length = len(self.messages) - 1
        if length > self.limit:
            del self.messages[1: length - self.limit + 1]

    def ask(self, prompt, retry=5) -> str:
        self.messages.append({"role": "user", "content": prompt})
        self._truncate_history()
        fail_cnt = 0
        while True:
            try:
                res = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=self.messages,
                )["choices"][0]["message"]
                break
            except Exception as e:
                fail_cnt += 1
                if fail_cnt > retry:
                    print("OpenAI API down!") 
                    return "Failed to reach ChatGPT!"
                print(f"Failed to access OpenAI API, count={fail_cnt}. Retrying...")

        self.messages.append({"role": res["role"], "content": res["content"]})
        return res["content"]
    
class GPTSessionManager:
    '''Stored session and its settings.'''
    def __init__(self, default_role):
        self.dir = Path("./data/session")
        if not os.path.exists(str(self.dir)):
            os.makedirs(str(self.dir))
        self.default_role = default_role
        
    def get(self, name) -> GPTSession:
        '''Get a specific session by name.'''
        filename = str(self.dir / (name + ".pkl"))
        if os.path.exists(filename):
            try:
                with open(filename, 'rb') as f:
                    session = pickle.load(f)
            except EnvironmentError:
                raise DBError("Loading pickle failed!")
        else:
            session = GPTSession(id=name, role=self.default_role)
        return session
    
    def writeback(self, session:GPTSession):
        '''Writeback a session.'''
        filename = str(self.dir / (session.id + ".pkl"))
        try:
            with open(filename, 'wb') as f:
                pickle.dump(session, f)
        except EnvironmentError:
            raise DBError("Dumping pickle failed!")
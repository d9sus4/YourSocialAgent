import os
import openai
from chatgpt_wrapper import ChatGPT
from revChatGPT.V1 import Chatbot

openai.api_key = "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" # mine
# openai.api_key = "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" # prnake
config={"email": "prnake@gmail.com", "password": ",ejhpQc%Q4+&$9T"}

prompt_example = "The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you today?\nHuman: "
start_sequence = "\nAI:"
restart_sequence = "\nHuman: "

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

elif CHATGPT_API == "OpenAI":
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
    ]
    num_message_limit = 100

    def set_num_message_limit(num: int):
        num_message_limit = num

    def set_chatgpt_role(role: str):
        '''Set ChatGPT's role as {role}. This will clear chat history.'''
        clear_chatgpt_history()
        messages[0]["content"] = f"You are {role}."

    def clear_chatgpt_history():
        messages = messages[:1]

    def _truncate_chatgpt_history():
        length = len(messages) - 1
        if length > num_message_limit:
            del messages[1: length - num_message_limit + 1]

    def ask_chatgpt(prompt, retry=5):
        messages.append({"role": "user", "content": prompt})
        _truncate_chatgpt_history()
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

        messages.append({"role": res["role"], "content": res["content"]})
        return res["content"]

else:
    raise NotImplementedError()
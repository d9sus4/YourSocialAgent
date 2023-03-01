import os
import openai
from chatgpt_wrapper import ChatGPT
from revChatGPT.V1 import Chatbot

openai.api_key = "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"
config={"email": "prnake@gmail.com", "password": ",ejhpQc%Q4+&$9T"}

prompt_example = "The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you today?\nHuman: "
start_sequence = "\nAI:"
restart_sequence = "\nHuman: "

CHATGPT_API = ["chatgpt_wrapper", "rev_chatgpt"][1]

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
else:
    rev_chatgpt = Chatbot(config=config)
    def ask_chatgpt(prompt):
        for data in rev_chatgpt.ask(prompt): # generator
            res = data["message"]
        return res
import os
import cmd
import llm
from chatlog_manager import ChatlogManager
from prompt_manager import PromptManager
from error import *

# DB managers
chatlog_manager = ChatlogManager()
prompt_manager = PromptManager()

VERBOSE = True
def verbose(*args):
    if VERBOSE:
        print(*args)

def clear_chatlog(person: str) -> bool:
    '''Clear chat logs with a person. Return bool indicating success / failure.'''
    try:
        chatlog_manager.clear(person)
        verbose("Chatlog cleared!")
        return True
    except DBError as e:
        verbose(e)
        return False

def clear_prompt(person: str) -> bool:
    '''Clear prompts of a person. Return bool indicating success / failure.'''
    try:
        prompt_manager.clear(person)
        verbose("Prompt cleared!")
        return True
    except DBError as e:
        verbose(e)
        return False

def suggest_reply(person: str, model: str, n_replies: int, keywords: list=[]) -> list:
    '''Suggest replies to a person. Return None if anything goes wrong'''
    if model == "chatgpt":
        prompt = "The following is an instant messaging conversation between another person and me.\n"
        # read personal prompts
        try:
            personal_prompts = prompt_manager.read_all(person)
        except DBError as e:
            verbose(e)
            return None
        
        for line in personal_prompts:
            prompt += line + '\n'
        prompt += '\n'
        # read chatlogs
        try:
            msgs = chatlog_manager.read_all(person)
        except DBError as e:
            verbose(e)
            return None
        for msg in msgs:
            prompt += msg["from"] + ": " + msg["text"] + '\n'
        prompt += "\n"
        prompt += f"Now, please compose {n_replies} possible reply message(s) based on the given context, in the same language as the conversation above. \n"
        prompt += "Please list only one message for each line without numbering it. \n"
        prompt += "Do not include any extra content, such as a translation, or a leading paragraph in your response. \n"
        prompt += "Just list the reply message texts straightly. \n"
        # prompting keywords
        if len(keywords) > 0:
            prompt += "Furthermore, the following keywords should be included in all the message(s) you compose for me: "
            for keyword in keywords:
                prompt += keyword + ", "
            prompt = prompt[:-2] + ". \n"
        verbose("Sending following prompt to ChatGPT:", prompt)
        res = llm.ask_chatgpt(prompt)
        raw_res = res

        # post-processing the response from ChatGPT
        try:
            res = res.splitlines()
            # 1. eliminate empty lines
            for i in range(len(res)-1, -1, -1):
                res[i] = res[i].strip()
                if len(res[i]) < 1:
                    del res[i]
            # 2. eliminate possible leading paragraph, e.g. "Possible messages: "
            if len(res) > 0 and res[0].strip()[-1] == ":":
                res = res[1:]
            # 3. eliminate translations
            # 4. delete leading "#." or "-"
            for i in range(len(res)-1, -1, -1):
                res[i] = res[i].strip()
                if len(res[i]) > 11 and res[i][:11].lower() == "translation":
                    del res[i]
                if res[i].split(' ', 1)[0] == "-" or (len(res[i].split()[0]) > 1 and res[i].split()[0][-1] == '.'):
                    res[i] = res[i].split(' ', 1)[1]
                    
        except IndexError:
            verbose("Index error!", "Maybe ChatGPT responded something unexpected that couldn't be processed.", f"Raw response: {raw_res}")
            return None
        
    elif model == "davinci":
        prompt = "The following is a conversation between another person and me.\n"
        try:
            personal_prompts = prompt_manager.read_all(person)
        except DBError as e:
            verbose(e)
            return None
        for line in personal_prompts:
            prompt += line + '\n'

        prompt += '\n'

        msgs = chatlog_manager.read_all(person)
        for msg in msgs:
            prompt += msg["from"] + ": " + msg["text"] + '\n'
        prompt += "I: "

        verbose("Sending following prompt to davinci-003:", prompt)
        
        res = llm.davinci_complete(prompt, top_p=n_replies)

    else:
        verbose(f"Unknown model: {model}.")
        return None
    
    return res

def read_chatlog(person: str) -> list:
    '''Read chat logs of a person. Return None if anything goes wrong.'''
    try:
        data = chatlog_manager.read_all(person)
        return data
    except DBError as e:
        verbose(e)
        return None

def read_prompt(person: str) -> list:
    '''Read prompts of a person. Return None if anything goes wrong.'''
    try:
        data = prompt_manager.read_all(person)
        return data
    except DBError as e:
        verbose(e)
        return None
    
def new_message(person: str, text: str, send: bool=False) -> bool:
    '''Receive or send a new message. Return bool indicating success / failure.'''
    try:
        chatlog_manager.add(text, person, send=send)
        return True
    except DBError as e:
        verbose(e)
        return False

def new_prompt(person: str, prompt: str) -> bool:
    '''Add prompt to a person. Return bool indicating success / failure.'''
    try:
        prompt_manager.add(prompt, person)
        return True
    except DBError as e:
        verbose(e)
        return False
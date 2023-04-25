"""All apis to interact with DB / LLM"""
import os
import re
import cmd
from llm import davinci_complete, ask_chatgpt, GPTSession
from chatlog_manager import ChatlogManager
from prompt_manager import PromptManager
from param_manager import ParamManager, ParamVector
from error import *

# DB managers
chatlog_manager = ChatlogManager()
prompt_manager = PromptManager()
param_manager = ParamManager()

VERBOSE = True

def verbose(*args):
    if VERBOSE:
        print(*args)

def switch_user(newuser: str) -> bool:
    '''Switch user in all managers. Return bool indicating success / failure.'''
    chatlog_manager.set_user(newuser)
    prompt_manager.set_user(newuser)
    param_manager.set_user(newuser)
    return True
        
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

def infer_hint_type(context: list, hint: str) -> str:
    '''context is a list of dicts and each dict is {"from": either "I" or "They", "text": "something"};
    usually it will have a short length such as 1 or 2.
    hint is what user types in.
    This function will let the LLM determine whether the hint belongs to "keyword" or "intention".
    '''
    prompt = r"""During conversation, human tends to come up with some simple but straight thoughts at first, then organize and accomplish them into natural language.
Thoughts can either be keywords or intentions. For example:

A: 你能简单介绍一下《原神》吗？
B: 好啊。
Thoughts of B: 米哈游 开放世界
B later: 《原神》是一款由米哈游开发的开放世界游戏。

This is an example of B organizing keyword thoughts into a response. Keyword thoughts are usually multiple phrases or concepts that are somehow related to the current topic or context of the conversation, and you can easily fulfill a sentence in natural language by connecting them up;

A: 你能简单介绍一下《原神》吗？
Thoughts of B: 委婉地拒绝
B later: 不好意思，我没有玩过《原神》，所以我并不了解它。

This is an example of B organizing intention thoughts into a response. Intention thoughts are general ideas or motivations that best decribe the following action the person takes.

Now I will provide you a conversation between A and B, where A said something, and B came up with some thoughts about it. You will determine which type of thoughts they belong to.
You can demonstrate your reasoning process, but the last line of your response should be a word of conclusion: either "keyword" or "intention".
So your response should follow this format:

Reason: your train of thought here
a single word "keyword" or "intention" here

Here's the conversation:

"""
    for message in context:
        prompt += {"I": "B: ", "They": "A: "}[message["from"]]
        prompt += message["text"]
        prompt += '\n'
    prompt += "Thoughts of B: "
    prompt += hint
    verbose("Sending following prompt to ChatGPT:")
    verbose(prompt)
    session = GPTSession()
    res = session.ask(prompt)
    verbose("ChatGPT replies:")
    verbose(res)
    res = res.lower().splitlines()[-1]
    if res.find("keyword") >= 0:
        verbose("Hint type: keyword")
        return "keyword"
    verbose("Hint type: intention")
    return "intention"
    
def suggest_reply(person: str, model: str, n_replies: int, keywords: list=[], intention: str=None) -> list:
    '''Suggest replies to a person. Return None if anything goes wrong.'''
    verbose("Now asking LLM for reply suggestions.")
    if model == "chatgpt": # prompt is constructed through multiple steps
        
        prompt = "You are an assisant that helps me handle my social relationships and communications with my contacts."
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
        prompt += "Now, I want to continue the conversation above.\n"
        prompt += f"You will compose {n_replies} possible message(s) that I can use, in the language of the conversation.\n"
        prompt += "You should learn the context and patterns from previous dialogues to make sure the messages you compose best resemble the way I talk.\n"
        prompt += "You will list only one message per line.\n"
        prompt += "Do not number them. Do not include any extra content, such as a translation or a leading paragraph. Just give me the message texts straightly.\n"
        
        # prompting parameters
        try:
            pv = param_manager.get("contact", person)
        except DBError as e:
            verbose(e)
            return None
        param_prompts, _, _ = pv.sample()
        if len(param_prompts) > 0:
            prompt += "Additionally, every message you compose must have: "
            for line in param_prompts:
                prompt += line + ", "
            prompt = prompt[:-1] + ".\n"
        
        # prompting intention
        if intention is not None:
            prompt += "Additionally, every message you compose should express the following intention: "
            prompt += intention
            prompt += '\n'
        # prompting keywords
        if len(keywords) > 0:
            prompt += "Additionally, the following keywords should be included in every message you compose: "
            for keyword in keywords:
                prompt += keyword + ", "
            prompt = prompt[:-2] + ". \n"
        verbose("Sending following prompt to ChatGPT:")
        verbose(prompt)
        session = GPTSession()
        res = session.ask(prompt)
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
        
        res = davinci_complete(prompt, top_p=n_replies)

    else:
        verbose(f"Unknown model: {model}.")
        return None
    
    return res

def read_chatlog(person: str, recent_n: int=0) -> list:
    '''Read chat logs of a person. Return None if anything goes wrong.'''
    try:
        data = chatlog_manager.read_all(person)
        return data[-recent_n:]
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

def parse_feedback(feedback: str): # legacy
    '''Parse feedback from user in natural language. return None if anything unexpected happens.
    Legacy, do not use'''
    prompt = "Here's a human user's feedback comment about texts generated by AI. Find out which parameter the user is not satisfied with and determine whether the user want it to be higher or lower.\n"
    prompt += 'You can explain your reasoning, but the last 2 lines in your response should be: name of the parameter (a noun word or phrase in English), and a single word "higher"" or "lower".\n'
    prompt += 'For example, if the feedback comment is "太啰嗦了", this is how your response may look like:\n'
    prompt += 'The user is not satisfied with the level of verbosity or wordiness of the text generated by AI. The user wants it to be lower, which means less wordy and more concise.\n'
    prompt += 'verbosity\n'
    prompt += 'lower\n\n'
    prompt += "Here's the feedback comment you will work on:\n"
    prompt += feedback
    verbose("Sending following prompt to ChatGPT:")
    verbose(prompt)
    session = GPTSession
    session.ask(prompt)
    verbose("ChatGPT replies:")
    verbose(res)
    res = res.lower().splitlines()
    if len(res) < 2:
        return None
    param = res[-2]
    param = param.strip()
    re.sub(r"[^a-z ]+", '', param)
    adjust = res[-1]
    if adjust.find("lower") >= 0:
        return param, "lower"
    elif adjust.find("higher") >= 0:
        return param, "higher"
    else:
        return None
    
def match_key(key, wordlist: list[str]): # legacy
    '''Match key in a word list. Ambiguously.
    Legacy, do not use'''
    prompt = "I will provide you with a keyword and a numbered list of words. Find the synonym of the keyword in the list.\n"
    prompt += "If there are multiple synonyms, find the one with the closest meaning.\n"
    prompt += 'You can explain your reasoning, but the last line of your response should be the number of the word you find in the list.\n'
    prompt += "If none of the words in the list is a proper synonym of the given keyword, return 0.\n\n"
    prompt += "Word list:\n"
    for i, word in enumerate(wordlist):
        prompt += f"{str(i+1)}. {word}\n"
    prompt += "\nKeyword:\n"
    prompt += key
    verbose("Sending following prompt to ChatGPT:")
    verbose(prompt)
    session = GPTSession()
    res = session.ask(prompt)
    verbose("ChatGPT replies:")
    verbose(res)
    return None

def feedback2commands(feedback: str, param_list: list[str]):
    ''' Convert human feedback (in natural language) in to commands.
    All possible commands:
    start
    end
    init <param>
    higher <param>
    lower <param>
    '''
    prompt = r"""You are controlling a text generation system designed for human users.
When the generated content does not satisfy human users, they may provide a feedback via natural language. In the meantime, you have a list of adjustable parameters in which the user is interested. It is your job to determine how to manipulate those parameters, according to the human feedback, in order to generate more satisfying results next time.
The parameter list can be manipulated using a set of commands. All possible commands and their explanations are listed below:

start: start the manipulation.
init <parameter_name>: init a new parameter.
lower <parameter_name>: lower the value of a parameter.
higher <parameter_name>: higher the value of a parameter.
end: end the manipulation.

Here are some example cases of converting a natural language feedback to a sequence of commands.
Inputs are current parameters and feedback; outputs are analyze and command sequence.
It is important that each case is treated individually:

-----Example Case 1-----
Current parameters:
politeness
seriousness
verbosity

Feedback:
太啰嗦了

Analyze:
The user indicated that the generated content was too verbose, so parameter "verbosity" should be lowered.

Command sequence:
start
lower verbosity
end

-----Example Case 2-----
Current parameters:
politeness
seriousness
verbosity

Feedback:
多用点表情符号

Analyze:
The user expected the generated content to have more emojis. There was no parameter in the list related to this, so init a new parameter named "emoji usage" first, and higher it.

Command sequence:
start
init emoji usage
higher emoji usage
end

-----Example Case 3-----
Current parameters:
politeness
seriousness
verbosity
emoji usage

Feedback:
大家好啊，我是说的道理

Analyze:
The user provided an incomprehensible feedback which had nothing to do with text generation. Maybe it was out of the user's misoperation, hence do nothing.

Command sequence:
start
end

-----Example Case 4-----
Current parameters:
politeness
seriousness
verbosity
emoji usage

Feedback:
注意我的语气词

Analyze:
The user expected the system to focus on the user's usage of modal particles. So init a new parameter of interest "modal particle usage", without lowering or highering it at current stage.

Command sequence:
start
init modal particle usage
end

Now, the system is initialized, and you must forget what used to be in the parameter list in the examples above.
You will work on a new case. I will give you current parameters and the feedback, and you will give me the analyze and command sequence.

-----The New Case-----
"""
    prompt += "\nCurrent parameters:\n"
    for param in param_list:
        prompt += param + '\n'
    prompt += "\nFeedback:\n"
    prompt += feedback + '\n'
    prompt += "\nAnalyze:\n"
    session = GPTSession()
    verbose("Sending following prompt to ChatGPT:")
    verbose(prompt)
    res = session.ask(prompt)
    verbose("ChatGPT replies:")
    verbose(res)
    res = res.lower()
    start_pos = res.find("command sequence:")
    if start_pos == -1:
        res = session.ask("Command sequence:\n")
    else:
        res = res[start_pos+len("command sequence:"):]
    lines = [line for line in res.splitlines() if line.strip()]
    return lines

def update_param(scope: str, identifier: str, feedback_commands):
    '''Execute feedback command on a param file.'''
    verbose("Updating params...")
    try:
        pv = param_manager.get(scope, identifier)
        verbose("Previous params:")
        verbose(str(pv))
        for line in feedback_commands:
            slots = line.split(' ', 1)
            if slots[0] == "init":
                pv.init_new_param(slots[1])
            elif slots[0] == "higher":
                pv.higher_param(slots[1])
            elif slots[0] == "lower":
                pv.lower_param(slots[1])
        verbose("Current params:")
        verbose(str(pv))
        param_manager.writeback(pv)
        return True
    except DBError as e:
        verbose(e)
        return False
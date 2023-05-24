"""All apis to interact with DB / LLM"""
import os
import re
import cmd
import openai
from llm import davinci_complete, ask_chatgpt, GPTSession
from chatlog_manager import ChatlogManager
from prompt_manager import PromptManager
from param_manager import ParamManager, ParamVector, LEVELS
from error import *
from typing import *
from meta import *
from multiprocessing import Pool
from threading import Thread
from datetime import datetime, timedelta
import pytz
import numpy as np

# DB managers
chatlog_manager = ChatlogManager()
prompt_manager = PromptManager()
param_manager = ParamManager()

VERBOSE = True
EMBEDDING_MODEL = "text-embedding-ada-002"
NUM_LOCAL_CHATLOG_MESSAGES = 20
INFERENCE_WINDOW_SIZE = 5
DEFAULT_TIMEZONE = pytz.timezone('Asia/Shanghai')
AUTO_EMBED = False
EMBED_INTERVAL = 900 # seconds, new message coming after this interval will be a block divider, previous block will be embedded
EMBED_DIMENSION = 1536
K_NEARST = 10

# module switches
RETRIEVED_CHATLOGS_ON = True

def verbose(*args):
    if VERBOSE:
        print(*args)

def get_user()->str:
    '''Get current user.'''
    return chatlog_manager.user

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

def infer_hint_type(person: str, hint: str) -> str:
    '''hint: whatever user types in.
    This function will let the LLM determine whether the hint belongs to "keyword" or "intention".
    '''
    context = chatlog_manager.read_chatlog(person, -INFERENCE_WINDOW_SIZE)
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
    
def suggest_replies(person: str, model: str, n_replies: int, keywords: list=[], intention: str=None) -> list: # legacy
    '''Suggest replies to a person. Return None if anything goes wrong.'''
    verbose("Now asking LLM for reply suggestions.")
    if model == "chatgpt": # prompt is constructed through multiple steps
        
        prompt = "You are an assisant that helps me handle my social relationships and communications with my contacts.\n"
        prompt += "The following is an instant messaging conversation between another person and me.\n"
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

def _ask_once(prompt):
        verbose("Sending following prompt to ChatGPT:")
        verbose(prompt)
        session = GPTSession()
        reply = session.ask(prompt)
        return reply

def suggest_messages(person: str, num_replies: int, keywords: list=[], intention: str=None, randomness=0) -> List[str]:
    '''Suggest messages to a person. Return None if anything goes wrong.'''
    # try:
    verbose("Now asking ChatGPT for messaging suggestions.")
    #1 prompt is constructed through multiple steps
    instr_prompt = "You are an assisant that helps me message to my contacts.\n"
    instr_prompt += f"You are going to imitate my writing style and help me write a new message to send to one of my contact named: {person}.\n"
    verbose("Instruction prompt finished!")
    
    # read gender: "male" or "female" or None
    contact_gender = get_gender(person)
    if contact_gender is None:
        contact_gender = "other"

    #2 read personal prompts
    personal_prompt = ""
    personal_prompt_texts = prompt_manager.read_all(person)
    if len(personal_prompt_texts) > 0:
        personal_prompt = f"Here is some background information about {person}:\n"
        for line in personal_prompt_texts:
            personal_prompt += line + '\n'
    verbose("Personal prompt finished!")
        
    #4 prompting parameters
    pv = param_manager.get("contact", person)
    sampled_params = pv.sample(randomness=randomness, k=num_replies)
    param_prompts = []
    for params in sampled_params:
        param_prompt = "The message you write must have following characteristics: "
        flag = False
        for p in params.keys():
            level = LEVELS[params[p]]
            if level is not None:
                param_prompt += LEVELS[params[p]] + ' ' + p + ", "
                flag = True
        if flag:
            param_prompt = param_prompt[:-2] + ".\n"
            param_prompts.append(param_prompt)
        else:
            param_prompts.append("")
    verbose("Parameter prompt finished!")
    
    #5 prompting intention
    intention_prompt = ""
    if intention is not None:
        intention_prompt = "The message you write must express the following intention: "
        intention_prompt += intention
        intention_prompt += '\n'
    verbose("Intention prompt finished!")
    
    #6 prompting keywords
    keyword_prompt = ""
    if len(keywords) > 0:
        keyword_prompt = "And every one of the following keywords should be included in the message you write: "
        for keyword in keywords:
            keyword_prompt += keyword + ", "
        keyword_prompt = keyword_prompt[:-2] + ".\n"
    verbose("Keyword prompt finished!")
    
    #7 read local chatlogs
    final_prompt = "Here is the current context you will work on and you should write the new message in the same language as the previous conversation:\n"
    local_chatlog = chatlog_manager.read_all(person)[-NUM_LOCAL_CHATLOG_MESSAGES:]
    pronoun = {"male": "He", "female": "She", "other": "They"}[contact_gender]
    local_chatlog_str = chatlog_to_str(person, local_chatlog)
    final_prompt += local_chatlog_str
    final_prompt += "I: "
    verbose("Local chatlog prompt finished!")

    #3 retrieve related chatlogs
    retrieved_prompt = ""
    if RETRIEVED_CHATLOGS_ON:
        local_embed = get_embedding(local_chatlog_str)
        frags = find_nearest_k_fragments(local_embed) #[(person, si, ei)]
        if len(frags) > 0:
            retrieved_prompt = "Here are some related chatlog fragments where you may learn useful information about me and my contacts, as well as my writing style:\n"
            for i, (contact, si, ei) in enumerate(frags):
                retrieved_logs = read_chatlog(contact, si, ei)
                retrieved_prompt += f"Fragment #{i}, contact name = {contact}\n"
                retrieved_prompt += chatlog_to_str(contact, retrieved_logs)
    verbose("Retrieved prompt finished!")

    # assemble and send prompts
    all_prompts = []
    for i in range(num_replies):
        param_prompt = param_prompts[i]
        prompt_list = [instr_prompt, personal_prompt, retrieved_prompt, param_prompt, intention_prompt, keyword_prompt, final_prompt]
        prompt = "\n".join([x for x in prompt_list if len(x) > 0])
        all_prompts.append(prompt)
    res = []
    with Pool(num_replies) as pool:
        for reply in pool.map(_ask_once, [p for p in all_prompts]):
            res.append(reply)
    return res, sampled_params

    # except Exception as e:
    #     verbose(e)
    #     return None

def read_chatlog(person: str, start_index:int=None, end_index:int=None) -> list:
    '''Read chat logs of a person. Return None if anything goes wrong.'''
    try:
        data = chatlog_manager.read_chatlog(person, start_index, end_index)
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
    
def new_message(person: str, text: str, send: bool=False, timestamp=None) -> bool:
    '''Receive or send a new message. Return bool indicating success / failure.
    timestamp is in ISO format, "+xs", or None.'''
    try:
        now = datetime.now(DEFAULT_TIMEZONE)
        ts = now.isoformat()
        last_ts = read_meta("last_timestamp", get_user(), person)
        if timestamp is not None:
            if is_iso_timestamp(timestamp):
                ts = timestamp
            else:
                seconds = extract_num_from_plus_x_s_string(timestamp)
                if seconds is not None and is_iso_timestamp(last_ts):
                    dt = datetime.fromisoformat(last_ts)
                    new_dt = dt + timedelta(seconds=seconds)
                    ts = new_dt.isoformat()
        chatlog_manager.add(text, person, send=send, timestamp=ts)
        if AUTO_EMBED:
            if last_ts is not None:
                new_datetime = datetime.fromisoformat(ts)
                last_datetime = datetime.fromisoformat(last_ts)
                time_diff = (new_datetime - last_datetime).total_seconds()
                verbose(f"It's been {time_diff}s since the last message.")
                if time_diff >= EMBED_INTERVAL:
                    verbose("Starting new auto embedding thread...")
                    last_embed_end_index = read_meta("last_embed_end_index", get_user(), person)
                    embed_end_index = read_meta("counter", get_user(), person) - 1
                    if last_embed_end_index is None:
                        last_embed_end_index = 0
                    t = Thread(target=summarize_and_embed, args=(person, last_embed_end_index, embed_end_index))
                    t.start()
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

def update_param_by_commands(scope: str, identifier: str, feedback_commands):
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

def update_param_by_dict(scope: str, identifier: str, param_dict):
    '''Update param by dict'''
    verbose("Updating params...")
    try:
        pv = param_manager.get(scope, identifier)
        verbose("Previous params:")
        verbose(str(pv))
        pv.update(param_dict)
        verbose("Current params:")
        verbose(str(pv))
        param_manager.writeback(pv)
        return True
    except DBError as e:
        verbose(e)
        return False

def get_param_vector(scope: str, identifier: str):
    '''Get param vector'''
    try:
        pv = param_manager.get(scope, identifier)
        return pv
    except DBError as e:
        verbose(e)
        return None

def contact_description_to_prompts(person: str, des: str):
    prompt = r"""You are an assistant who generates memos for you on how to communicate through text messages with specific contacts.
I will give you the contact's name, gender, and a comment about the contact. You will summary my comment, infer the manners I should follow messaging to the contact, and write a memo in English for me. Avoid using pronouns like "he" or "she" in your memo, just use the contact's name, and keep the name in its original language if not English. Write the memo in my perspective. 
The process is as follows:

Contact name: Adam
Gender: male
Comment: He is my close friend
Memo: Adam is a close friend of mine. I can adopt a casual and informal tone communicating with him. I can be relaxed, friendly, and use a language style that reflects my familiarity and comfort with him.

Contact name: エリカ
Gender: female
Comment: 私の彼女です
Memo: エリカ is my girlfriend. I shall adopt a warm, affectionate, and intimate tone in most of the time. I can be more relaxed, playful, and use language that reflects the level of comfort and familiarity we have with each other.

Contact name: 李智
Gender: male
Comment: 他是我的博导
Memo: 李智 is my PhD advisor. It is important to adopt a respectful and formal tone for me when communicating with professors. Maintaining a professional and courteous tone is essential, while using polite language, addressing him with proper titles (such as "教授" or "Prof."), and following appropriate etiquette are also to be considered.

Contact name: Jane
Gender: female
Comment: She's my mom and I love her
Memo: Jane is my dearest mother. I shall adopt a respectful and affectionate tone, and show appreciation for her love, care, and guidance by speaking with kindness and consideration."

"""
    prompt += f"Contact name: {person}\n"
    prompt += f"Gender: {get_gender(person)}\n"
    prompt += f"Comment: {des}\n"
    prompt += "Memo: "
    verbose("Sending following prompt to ChatGPT:")
    verbose(prompt)
    session = GPTSession()
    res = session.ask(prompt)
    verbose("ChatGPT replies:")
    verbose(res)
    return res

def get_embedding(text, model=EMBEDDING_MODEL):
   text = text.replace("\n", " ")
   res = openai.Embedding.create(input = [text], model=model)['data'][0]['embedding']
   verbose(f"Got a new embedding of length {len(res)}.")
   return res

def set_gender(person: str, gender: str):
    '''gender: male or female or other'''
    write_meta("gender", gender, get_user(), person)

def get_gender(person: str):
    '''gender: male or female or other'''
    return read_meta("gender", get_user(), person)

def chatlog_to_str(person: str, logs: list):
    '''Ends with an extra empty line'''
    log_str = ""
    for log in logs:
        log_str += {"I": "I", "They": person}[log["from"]] + ": " + log["text"] + '\n'
    return log_str

def summarize_chatlog_fragment(person: str, start_index, end_index=None):
    '''Summarize a fragment of chatlog into a sentence. Return string.'''
    logs = chatlog_manager.read_chatlog(person, start_index=start_index, end_index=end_index)
    log_str = chatlog_to_str(person, logs)
    prompt = f"The following is a fragment of my chat log with {person}. You will summarize the topic of the conversation into one sentence in English. You will write from my perspective.\n\n"
    prompt += log_str
    prompt += "\nSummary (in English):"
    session = GPTSession()
    verbose("Sending following prompt to ChatGPT:")
    verbose(prompt)
    res = session.ask(prompt)
    verbose("ChatGPT replies:")
    verbose(res)
    return res

def summarize_and_embed(person: str, start_index, end_index=None):
    summary = summarize_chatlog_fragment(person, start_index=start_index, end_index=end_index)
    embed = get_embedding(summary)
    embed = np.array(embed)
    chatlog_manager.update_embed(embed, person, start_index=start_index, end_index=end_index)
    verbose(f"Embedding of {person} from {start_index} to {end_index} finished!")

def is_iso_timestamp(timestamp: str) -> bool:
    if timestamp is None:
        return False
    try:
        datetime.fromisoformat(timestamp)
        return True
    except ValueError:
        return False

def extract_num_from_plus_x_s_string(string: str):
    pattern = r"\+(\d+)s"
    match = re.match(pattern, string)
    if match:
        return int(match.group(1))
    else:
        return None

def find_nearest_k_fragments(embed:np.array, k:int=K_NEARST):
    '''From all chat logs of all contacts, find k fragments that have the nearest embedding vector to a given vector
    Return a list of (person, start_index, end_index) tuples'''
    all_embeds = chatlog_manager.get_all_embeds()
    contacts = all_embeds.keys()
    # print(contacts) # dict_keys(['Tom'])
    # print(type(all_embeds["Tom"])) # <class 'list'>
    # print(all_embeds["Tom"]) # [(array([ 0.00778798, -0.03730292,  0.0120602 , ..., -0.00377308, -0.00556195, -0.01985438]), 0, 4)]
    distances = []
    indices = [] # entry: (person, start_index, end_index) tuple
    for contact in contacts:
        for vec, si, ei in all_embeds[contact]:
            distance = np.linalg.norm(vec - embed)  # 计算欧几里得距离
            distances.append(distance)
            indices.append((contact, si, ei))
    k_indices = np.argsort(distances)[:k]
    k_nearest_frags = [indices[i] for i in k_indices]
    return k_nearest_frags

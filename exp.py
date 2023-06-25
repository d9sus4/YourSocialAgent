from api import *

rnd = 25
n_msgs = 3
switch_user("test")

def _ask_once(prompt):
        session = GPTSession()
        reply = session.ask(prompt)
        return reply

plist = []
mlist = []

ENABLE_PARAM_VECTOR = True

pv = param_manager.get("contact", "emoji")
pv.init_new_param("emoji usage frequency")
param_manager.writeback(pv)

for i in range(rnd):
    pv = param_manager.get("contact", "emoji")
    print(f"Rnd = {i}")
    print(f"Current vector = \n{str(pv)}")
    samples = pv.sample(randomness=1, k=3)

    instr_prompt = "Imagine you are using an instant messaging service, such as Telegram, Line or WeChat.\n"
    instr_prompt += "You will receive a message from another person and write a response.\n"
    instr_prompt += "You can use one or multiple <br> to break the messege, contents after <br> will be sent as another message card.\n"
    instr_prompt += "You can use emojis in your response.\n"

    param_prompts = []
    for params in samples:
        param_prompt = "The message you write must have following characteristics in text style: "
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

    final_prompt = "Message you receive: Was the film last night good? Tell me about it.😚\n"
    final_prompt += "Your response (use <br> to break): "


    all_prompts = []
    for i in range(n_msgs):
        param_prompt = param_prompts[i]
        prompt_list = [instr_prompt, param_prompt, final_prompt]
        prompt = "\n".join([x for x in prompt_list if len(x) > 0])
        all_prompts.append(prompt)
    res = []
    with Pool(n_msgs) as pool:
        for reply in pool.map(_ask_once, [p for p in all_prompts]):
            res.append(reply)
    
    if res is not None:
        print("LLM suggests:")
        for i in range(len(res)):
            print(f"{i+1}. {res[i]}\n\t({samples[i]})")
        choice = int('0' + input("Choose one: "))
        if choice in range(1, len(res)+1):
            update_param_by_dict("contact", "emoji", samples[choice-1])
            plist.append(samples[choice-1])
            mlist.append(res[choice-1])

pfile = "./data/test/p.json"
with open(pfile, 'w', encoding="utf8") as f:
    json.dump(plist, f, ensure_ascii=False)
mfile = "./data/test/m.json"
with open(mfile, 'w', encoding="utf8") as f:
    json.dump(mlist, f, ensure_ascii=False)

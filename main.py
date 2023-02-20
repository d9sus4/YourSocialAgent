import os
import api
import chatlog_manager
import prompt_manager

MODEL = ["davinci", "chatgpt"][1]
DEBUG = True

def main():
    person = None
    while True:
        hint = "Input a command: "
        if person is not None:
            hint = f"({person}) " + hint

        command = input(hint)
        slots = command.split(" ", 1)

        if len(slots) == 0:
            continue

        elif len(slots) == 1:

            if slots[0] == "quit":
                break

            elif slots[0] == "clear":
                if person is None:
                    print("Who are you chatting with?")
                    continue
                chatlog_manager.clear(person)
                print("Chatlog cleared!")
                continue

            elif slots[0] == "clearprompt":
                if person is None:
                    print("Who are you chatting with?")
                    continue
                prompt_manager.clear(person)
                print("Prompt cleared!")
                continue
            
            elif slots[0] == "clearall":
                if person is None:
                    print("Who are you chatting with?")
                    continue
                chatlog_manager.clear(person)
                prompt_manager.clear(person)
                print("Chatlog & prompt cleared!")
                continue

            elif slots[0] == "autocomp":
                if person is None:
                    print("Who are you chatting with?")
                    continue

                prompt = "The following is a conversation between I and another person.\n"
                personal_prompts = prompt_manager.read_all(person)
                for line in personal_prompts:
                    prompt += line + '\n'

                keywords = input("Please input keywords (enter to skip): ")
                keywords = keywords.strip().split()
                if len(keywords) > 0:
                    prompt += "I am going to send back something about: "
                    for keyword in keywords:
                        prompt += keyword + ", "
                    prompt = prompt[:-2] + '\n\n'

                msgs = chatlog_manager.read_all(person)
                for msg in msgs:
                    prompt += msg["from"] + ": " + msg["text"] + '\n'
                prompt += "I: "

                if DEBUG:
                    print(prompt)
                
                if MODEL == "davinci":
                    res = api.davinci_complete(prompt)[0]
                else:
                    res = api.chatgpt_complete(prompt)
                print("Auto-completion suggests:", res)
                if input("Is that OK? (y/n): ").strip() == "y":
                    chatlog_manager.add(res, person, send=True)
                    print("Message sent!")
                else:
                    print("Sorry about that!")
                continue

            elif slots[0] == "view":
                if person is None:
                    print("Who are you chatting with?")
                    continue
                data = chatlog_manager.read_all(person)
                print(f"Viewing all logs with {person}.")
                for msg in data:
                    print(msg["from"] + ": " + msg["text"])
                continue

            elif slots[0] == "viewprompt":
                if person is None:
                    print("Who are you chatting with?")
                    continue
                prompts = prompt_manager.read_all(person)
                print(f"Viewing all prompts of {person}.")
                for prompt in prompts:
                    print(prompt)
                continue

        elif len(slots) == 2:

            if slots[0] == "p":
                person = slots[1].strip()
                print(f"Chatting with {person}.")
                continue

            elif slots[0] in ["r", "s"]:
                if person is None:
                    print("Who are you chatting with?")
                    continue
                chatlog_manager.add(slots[1].strip(), person, send={"r":False, "s":True}[slots[0]])
                print({"r": "Message received.", "s": "Message sent."}[slots[0]])
                continue

            elif slots[0] == "addprompt":
                if person is None:
                    print("Who are you chatting with?")
                    continue
                prompt_manager.add(slots[1].strip(), person)
                print("Prompt added.")
                continue

        else:
            print("Unknown command!")


if  __name__ == "__main__":
    main()
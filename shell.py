import os
import cmd
import llm
from chatlog_manager import ChatlogManager
from prompt_manager import PromptManager
from api import *
class YSAShell(cmd.Cmd):
    """
    Your Social Agent Shell
    """
    # globals
    ALIAS = {
        "p": "person",
        "r": "receive",
        "s": "send",
        "q": "quit",
        "v": "view",
        "vp": "viewprompt",
        "c": "clear",
        "cp": "clearprompt",
        "ca": "clearall",
        "ap": "addprompt",
        "su": "suggest",
        "num": "numsuggest",
    }
    CHECK_PERSON = (
        "receive",
        "send",
        "clear",
        "clearall",
        "clearprompt",
        "suggest",
        "view",
        "viewprompt",
        "addprompt",
    )

    # overrides
    intro = "Your Social Agent Shell, type \"help\" for instructions."
    prompt = "(None) "

    def precmd(self, line):
        line = line.strip().split(' ', 1)
        line[0] = line[0].lower()
        if line[0] in self.ALIAS.keys():
            line[0] = self.ALIAS[line[0]]
        if line[0] in self.CHECK_PERSON and self.person is None:
            return "SET_A_PERSON_FIRST"
        return ' '.join(line)

    def default(self, line):
        if line == "SET_A_PERSON_FIRST":
            print("Who are you talking with? Indicate a person first.")
        else:
            print(f"Syntax error in line \"{line}\"!")

    # params
    person = None
    model = ["davinci", "chatgpt"][1]
    num_res = 3

    # commands
    # call Cmd.onecmd(str) to interpret a single command
    def do_quit(self, arg):
        "Quit Y.S.A. Shell."
        print("See you!")
        return True
    
    def do_person(self, arg):
        "Choose a person to talk with."
        self.person = arg.strip()
        print(f"Chatting with {self.person}.")
        self.prompt = f"({self.person}) "
    
    def do_clear(self, arg):
        "Clear chat logs with the current person."
        if clear_chatlog(self.person):
            print("Chatlog cleared!")
        else:
            print("Failed!")
    
    def do_clearprompt(self, arg):
        "Clear prompts of the current person."
        if clear_prompt(self.person):
            print("Prompt cleared!")
        else:
            print("Failed!")
    
    def do_clearall(self, arg):
        "Clear chat logs and prompts of the current person."
        self.do_clear()
        self.do_clearprompt()
    
    def do_suggest(self, arg):
        "Generate suggestions by LLM."

        keywords = input("Please input keywords (enter to skip): ")
        keywords = keywords.strip().split()

        res = suggest_reply(self.person, self.model, self.num_res, keywords=keywords)
        if res is not None:
            print("LLM suggests:")
            for i in range(len(res)):
                print(f"{i+1}. {res[i]}")
            try:
                choice = int('0' + input("Which one would you like to send? (0 for none): "))
                if choice in range(1, len(res)+1):
                    if new_message(self.person, res[choice], send=True):
                        print("Message sent!")
                    else:
                        print("Failed!")
                else:
                    print("Sorry about that!")
            except ValueError:
                print("Illegal input!")
        else:
            print("Failed!")

    def do_view(self, arg):
        "View all chat logs with the current person"
        data = read_chatlog(self.person)
        if data is not None:
            print(f"Viewing all logs with {self.person}.")
            for msg in data:
                print(msg["from"] + ": " + msg["text"]) 
        else:
            print("Failed!")

    def do_viewprompt(self, arg):
        "View all prompts of the current person."
        prompts = read_prompt(self.person)
        if prompts is not None:
            print(f"Viewing all prompts of {self.person}.")
            for prompt in prompts:
                print(prompt)
        else:
            print("Failed!")

    def do_receive(self, arg):
        "Receive a message from the current person."
        if new_message(self.person, arg, send=False):
            print("Message received.")
        else:
            print("Failed!")

    def do_send(self, arg):
        "Send a message to the current person"
        if new_message(self.person, arg, send=True):
            print("Message sent.")
        else:
            print("Failed!")
    
    def do_addprompt(self, arg):
        "Add a prompt to the current person."
        if new_prompt(self.person, arg):
            print("Prompt added.")
        else:
            print("Failed!")

    def do_model(self, arg):
        "Switch model."
        self.model = arg
        print(f"Model switched to {arg}.")

    def do_numsuggest(self, arg):
        "Set the number of generated suggestions."
        self.num_res = int(arg)
        print(f"Number of suggestions set to {arg}.")

    
def main():
    ysa = YSAShell()
    YSAShell().cmdloop()


if  __name__ == "__main__":
    main()
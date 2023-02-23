import os
import cmd
import api
from chatlog_manager import ChatlogManager
from prompt_manager import PromptManager
class YSAShell(cmd.Cmd):
    """
    Your Social Agent Shell
    """
    # globals
    ALIAS = {
        "p": "person",
        "r": "receive",
        "s": "send",
        "v": "view",
        "vp": "viewprompt",
        "c": "clear",
        "cp": "clearprompt",
        "ca": "clearall",
        "ap": "addprompt",
        "ac": "autocomp",
    }
    CHECK_PERSON = (
        "receive",
        "send",
        "clear",
        "clearall",
        "clearprompt",
        "autocomp",
        "view",
        "viewprompt",
        "addprompt",
    )
    MODEL = ["davinci", "chatgpt"][1]
    DEBUG = True

    # DB managers
    chatlog_manager = ChatlogManager()
    prompt_manager = PromptManager()

    # overrides
    intro = '''Your Social Agent Shell, type "help" for instructions.'''
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
            print(f'''Syntax error in line "{line}"!''')

    # params
    person = None

    # commands
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
        self.chatlog_manager.clear(self.person)
        print("Chatlog cleared!")
    
    def do_clearprompt(self, arg):
        "Clear prompts of the current person."
        self.prompt_manager.clear(self.person)
        print("Prompt cleared!")
    
    def do_clearall(self, arg):
        "Clear chat logs and prompts of the current person."
        self.chatlog_manager.clear(self.person)
        self.prompt_manager.clear(self.person)
        print("Chatlog & prompt cleared!")
    
    def do_autocomp(self, arg):
        "Do auto-completion through LLM."

        if self.MODEL == "chatgpt":
            prompt = "The following is a conversation between I and another person.\n"
            personal_prompts = self.prompt_manager.read_all(self.person)
            for line in personal_prompts:
                prompt += line + '\n'

            keywords = input("Please input keywords (enter to skip): ")
            keywords = keywords.strip().split()
            if len(keywords) > 0:
                prompt += "I am going to send back something about: "
                for keyword in keywords:
                    prompt += keyword + ", "
                prompt = prompt[:-2] + '\n\n'

            msgs = self.chatlog_manager.read_all(self.person)
            for msg in msgs:
                prompt += msg["from"] + ": " + msg["text"] + '\n'
            prompt += "I: "

            if self.DEBUG:
                print(prompt)

            res = api.chatgpt_complete(prompt)
        
        else:
            prompt = "The following is a conversation between I and another person.\n"
            personal_prompts = self.prompt_manager.read_all(self.person)
            for line in personal_prompts:
                prompt += line + '\n'

            prompt += '\n'

            msgs = self.chatlog_manager.read_all(self.person)
            for msg in msgs:
                prompt += msg["from"] + ": " + msg["text"] + '\n'
            prompt += "I: "

            if self.DEBUG:
                print(prompt)
            
            res = api.davinci_complete(prompt)[0]

        print("Auto-completion suggests:", res)
        if input("Is that OK? (y/n): ").strip() == "y":
            self.chatlog_manager.add(res, self.person, send=True)
            print("Message sent!")
        else:
            print("Sorry about that!")

    def do_view(self, arg):
        "View all chat logs with the current person"
        data = self.chatlog_manager.read_all(self.person)
        print(f"Viewing all logs with {self.person}.")
        for msg in data:
            print(msg["from"] + ": " + msg["text"])

    def do_viewprompt(self, arg):
        "View all prompts of the current person."
        prompts = self.prompt_manager.read_all(self.person)
        print(f"Viewing all prompts of {self.person}.")
        for prompt in prompts:
            print(prompt)

    def do_receive(self, arg):
        "Receive a message from the current person."
        self.chatlog_manager.add(arg, self.person, send=False)
        print("Message received.")

    def do_send(self, arg):
        "Send a message to the current person"
        self.chatlog_manager.add(arg, self.person, send=True)
        print("Message sent.")
    
    def do_addprompt(self, arg):
        "Add a prompt to the current person."
        self.prompt_manager.add(arg, self.person)
        print("Prompt added.")

    def do_model(self, arg):
        "Switch model."
        self.MODEL = arg
        print(f"Model switched to {arg}.")
    
    def do_debug(self, arg):
        self.DEBUG = not self.DEBUG
        print(f"DEBUG set to {str(self.DEBUG)}.")


def main():
    ysa = YSAShell()
    YSAShell().cmdloop()


if  __name__ == "__main__":
    main()
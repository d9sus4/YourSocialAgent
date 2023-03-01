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
    model = ["davinci", "chatgpt"][1]
    num_res = 3
    debug = True

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
    
    def do_suggest(self, arg):
        "Generate suggestions by LLM."

        if self.model == "chatgpt":
            prompt = '''The following is an instant messaging conversation between another person and me.\n'''
            personal_prompts = self.prompt_manager.read_all(self.person)
            for line in personal_prompts:
                prompt += line + '\n'
            prompt += '\n'

            msgs = self.chatlog_manager.read_all(self.person)
            for msg in msgs:
                prompt += msg["from"] + ": " + msg["text"] + '\n'
            prompt += "\n"

            prompt += f'''Now, please compose {self.num_res} possible reply message(s) based on the given context, in the same language as the conversation above. \n'''
            prompt += '''Please list only one message for each line without numbering it. \n''' 
            prompt += '''Do not include any extra content, such as a translation, or a leading paragraph in your response. \n'''
            prompt += '''Just list the reply message texts straightly. \n'''
            
            keywords = input("Please input keywords (enter to skip): ")
            keywords = keywords.strip().split()
            if len(keywords) > 0:
                prompt += "Furthermore, the following keywords should be included in all the message(s) you compose for me: "
                for keyword in keywords:
                    prompt += keyword + ", "
                prompt = prompt[:-2] + ". \n"

            if self.debug:
                print(prompt)

            res = api.chatgpt_complete(prompt)
            raw_res = res

            # post-processing the response from ChatGPT
            try:
                res = res.splitlines()
                # 1. eliminate possible leading paragraph, e.g. "Possible messages: "
                if res[0].strip()[-1] == ":":
                    res = res[1:]
                # 2. eliminate empty lines
                # 3. eliminate translations
                # 4. delete leading "#." or "-"
                for i in range(len(res)-1, -1, -1):
                    res[i] = res[i].strip()
                    if len(res[i]) < 1 or (len(res[i]) > 11 and res[i][:11].lower() == "translation"):
                        del res[i]
                    if res[i].split(' ', 1)[0] == "-" or (len(res[i].split()[0]) > 1 and res[i].split()[0][-1] == '.'):
                        res[i] = res[i].split(' ', 1)[1]
                        
            except IndexError:
                res = ["Index error!", "Maybe ChatGPT responded something unexpected that couldn't be processed.", f"Raw response: {raw_res}"]

        
        else:
            prompt = "The following is a conversation between another person and me.\n"
            personal_prompts = self.prompt_manager.read_all(self.person)
            for line in personal_prompts:
                prompt += line + '\n'

            prompt += '\n'

            msgs = self.chatlog_manager.read_all(self.person)
            for msg in msgs:
                prompt += msg["from"] + ": " + msg["text"] + '\n'
            prompt += "I: "

            if self.debug:
                print(prompt)
            
            res = api.davinci_complete(prompt)[:self.num_res]

        print("LLM suggests:")
        for i in range(len(res)):
            print(f"{i+1}. {res[i]}")
        try:
            choice = int('0' + input("Which one would you like to send? (0 for none): "))
            if choice in range(1, len(res)+1):
                self.chatlog_manager.add(res[choice], self.person, send=True)
                print("Message sent!")
            else:
                print("Sorry about that!")
        except ValueError:
            print("Illegal input!")

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
        self.model = arg
        print(f"Model switched to {arg}.")
    
    def do_debug(self, arg):
        "Enable / disable debugging."
        self.debug = not self.debug
        print(f"debug set to {str(self.debug)}.")

    def do_numsuggest(self, arg):
        "Set the number of generated suggestions."
        self.num_res = int(arg)
        print(f"Number of suggestions set to {arg}.")

    
def main():
    ysa = YSAShell()
    YSAShell().cmdloop()


if  __name__ == "__main__":
    main()
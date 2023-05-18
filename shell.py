import cmd
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
        "fb": "feedback",
        "t": "test", # used for API test only
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
        "feedback",
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
        # check if person has prompt. if not, guide user to add some:
        prompts = read_prompt(self.person)
        if prompts is not None and len(prompts) == 0:
            print (f"It seems you are chatting with a new contact.")
            try:
                choice = int(input(f"What is {self.person}'s gender? (1: male; 2: female; 0: other): "))
                set_gender(self.person, ["other", "male", "female"][choice])
            except ValueError:
                print("Illegal input!")
            while True:
                des = input(f"Describe {self.person}'s relationship to you (enter to finish): ")
                if len(des) > 0:
                    new_prompt(self.person, contact_description_to_prompts(self.person, des))
                else:
                    break
    
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
        hint = input("Please input hint (enter to skip): ")
        keywords = []
        intention = None
        if len(hint) > 0:
            hint_type = infer_hint_type(read_chatlog(self.person, 5), hint)
            if hint_type == "keyword":
                keywords = hint.strip().split()
                intention = None
            else:
                keywords = []
                intention = hint
        res = suggest_messages(self.person, self.num_res, keywords=keywords, intention=intention, randomness=0)
        if res is not None:
            print("LLM suggests:")
            for i in range(len(res)):
                print(f"{i+1}. {res[i]}")
            try:
                choice = int('0' + input("Which one would you like to send? (0 for none): "))
                if choice in range(1, len(res)+1):
                    if new_message(self.person, res[choice-1], send=True):
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

    def do_numsuggest(self, arg):
        "Set the number of generated suggestions."
        self.num_res = int(arg)
        print(f"Number of suggestions set to {arg}.")
    
    def do_feedback(self, arg):
        pv = param_manager.get("contact", self.person)
        commands = feedback2commands(arg, pv.get_all_param_names())
        update_param_by_commands("contact", self.person, commands)
    
    def do_test(self, arg):
        "Used for API testing only."
        print(feedback2commands("注意标点符号的用法", ["verbosity"]))

    
def main():
    ysa = YSAShell()
    YSAShell().cmdloop()


if  __name__ == "__main__":
    main()
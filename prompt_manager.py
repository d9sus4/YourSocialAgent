import os
import json
from pathlib import Path
from error import *

class PromptManager:

    def __init__(self):
        self.set_user("default")

    def set_user(self, user):
        self.dir = Path("./data") / user / "prompt"
        if not os.path.exists(str(self.dir)):
            os.makedirs(str(self.dir))

    def add(self, prompt, person):
        data = []
        filename = str(self.dir / (person + ".json"))
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding="utf8") as f:
                    data = json.load(f)
            except EnvironmentError:
                raise DBError("Loading json failed!")
        data.append(prompt.strip())
        try:
            with open(filename, 'w', encoding="utf8") as f:
                data = json.dump(data, f, ensure_ascii=False)
        except EnvironmentError:
            raise DBError("Dumping json failed!")

    def read_all(self, person):
        data = []
        filename = str(self.dir / (person + ".json"))
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding="utf8") as f:
                    data = json.load(f)
            except EnvironmentError:
                raise DBError("Loading json failed!")
        return data

    def clear(self, person):
        filename = str(self.dir / (person + ".json"))
        if os.path.exists(filename):
            try:
                with open(filename, 'w', encoding="utf8") as f:
                    json.dump([], f, ensure_ascii=False)
            except EnvironmentError:
                raise DBError("Clearing prompt failed!")
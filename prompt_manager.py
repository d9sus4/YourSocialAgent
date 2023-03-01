import os
import json
from pathlib import Path
from error import *

class PromptManager:
    def __init__(self, filename=str(Path("./data/prompt.json"))):
        self.filename = filename

    def add(self, prompt, person):
        data = {}
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding="utf8") as f:
                    data = json.load(f)
            except EnvironmentError:
                raise DBError("Loading json failed!")
        if person not in data.keys():
            data[person] = []
        data[person].append(prompt.strip())
        try:
            with open(self.filename, 'w', encoding="utf8") as f:
                data = json.dump(data, f, ensure_ascii=False)
        except EnvironmentError:
            raise DBError("Dumping json failed!")

    def read_all(self, person):
        data = {}
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding="utf8") as f:
                    data = json.load(f)
            except EnvironmentError:
                raise DBError("Loading json failed!")
        if person in data.keys():
            return data[person]
        else:
            return []

    def clear(self, person):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding="utf8") as f:
                    data = json.load(f)
                    if person in data.keys():
                        data.pop(person)
                with open(self.filename, 'w', encoding="utf8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except EnvironmentError:
                raise DBError("Clearing prompt failed!")
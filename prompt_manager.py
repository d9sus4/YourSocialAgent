import os
import json
from pathlib import Path
prompt_file = str(Path("./data/prompt.json"))

def add(prompt, person):
    data = {}
    if os.path.exists(prompt_file):
        try:
            with open(prompt_file, 'r', encoding="utf8") as f:
                data = json.load(f)
        except EnvironmentError:
            print("Loading json failed!")
    if person not in data.keys():
        data[person] = []
    data[person].append(prompt.strip())
    try:
        with open(prompt_file, 'w', encoding="utf8") as f:
            data = json.dump(data, f, ensure_ascii=False)
    except EnvironmentError:
        print("Dumping json failed!")

def read_all(person):
    data = {}
    if os.path.exists(prompt_file):
        try:
            with open(prompt_file, 'r', encoding="utf8") as f:
                data = json.load(f)
        except EnvironmentError:
            print("Loading json failed!")
    if person in data.keys():
        return data[person]
    else:
        return []

def clear(person):
    if os.path.exists(prompt_file):
        try:
            with open(prompt_file, 'r', encoding="utf8") as f:
                data = json.load(f)
                if person in data.keys():
                    data.pop(person)
            with open(prompt_file, 'w', encoding="utf8") as f:
                json.dump(data, f, ensure_ascii=False)
        except EnvironmentError:
            print("Clearing prompt failed!")
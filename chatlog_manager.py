import os
import json
from pathlib import Path

chatlog_dir = Path("./data")

def add(text, person, send):
    filename = str(chatlog_dir / (person + ".json"))
    data = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding="utf8") as f:
                data = json.load(f)
        except EnvironmentError:
            print("Loading json failed!")
    data.append({"from": "I" if send else "They", "text": text})
    try:
        with open(filename, 'w', encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False)
    except EnvironmentError:
        print("Dumping json failed!")

def read_all(person):
    filename = str(chatlog_dir / (person + ".json"))
    data = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding="utf8") as f:
                data = json.load(f)
        except EnvironmentError:
            print("Loading json failed!")
    return data

def clear(person):
    filename = str(chatlog_dir / (person + ".json"))
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except EnvironmentError:
            print("Clearing chatlog failed!")
# for store and fast retrieve meta data using key pair <user, contact>
# all meta files are in json of python dictionary
from pathlib import Path
import os
import json
from error import *

meta_dir = Path("./data") / "meta"
if not os.path.exists(str(meta_dir)):
    os.makedirs(str(meta_dir))

def read_meta(key, user, contact):
    filename = str(meta_dir / f"{user}-{contact}.json")
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding="utf8") as f:
                data = json.load(f)
        except EnvironmentError:
            raise DBError("Loading json failed!")
        return data.get(key, None)
    return None

def write_meta(key, value, user, contact):
    filename = str(meta_dir / f"{user}-{contact}.json")
    data = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding="utf8") as f:
                data = json.load(f)
        except EnvironmentError:
            raise DBError("Loading json failed!")
    data[key] = value
    try:
        with open(filename, 'w', encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False)
    except EnvironmentError:
        raise DBError("Dumping json failed!")
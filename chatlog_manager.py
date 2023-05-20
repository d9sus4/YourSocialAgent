import os
import json
import pickle
from pathlib import Path
from error import *
import numpy as np
from meta import *
from datetime import datetime


class ChatlogManager:

    def __init__(self):
        self.set_user("default")

    def set_user(self, user):
        self.user = user
        self.dir = Path("./data") / user / "chatlog"
        if not os.path.exists(str(self.dir)):
            os.makedirs(str(self.dir))
        self.embed_dir = Path("./data") / user / "embed"
        if not os.path.exists(str(self.embed_dir)):
            os.makedirs(str(self.embed_dir))

    def add(self, text, person, send, timestamp:str):
        '''it's caller's responsibility to ensure timestamp is str in YYYY-MM-DDTHH:MM:SSZ (ISO-8601)'''
        filename = str(self.dir / (person + ".json"))
        data = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding="utf8") as f:
                    data = json.load(f)
            except EnvironmentError:
                raise DBError("Loading json failed!")
        data.append({"from": "I" if send else "They", "text": text, "time": timestamp})
        try:
            with open(filename, 'w', encoding="utf8") as f:
                json.dump(data, f, ensure_ascii=False)
        except EnvironmentError:
            raise DBError("Dumping json failed!")
        write_meta("counter", len(data), self.user, person)
        write_meta("last_timestamp", timestamp, self.user, person)

    def read_all(self, person):
        return self.read_chatlog(person)
    
    def read_chatlog(self, person, start_index:int=None, end_index:int=None):
        filename = str(self.dir / (person + ".json"))
        data = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding="utf8") as f:
                    data = json.load(f)
            except EnvironmentError:
                raise DBError("Loading json failed!")
        return data[start_index: end_index]

    def update_embed(self, embed:np.array, person, start_index:int=None, end_index:int=None):
        '''embed from start to end
        each embed is a EMBED_DIMENSION-dim numpy array, stored in a list in a dict in a pickle
        return bool: success or failure
        '''
        if start_index is None:
            start_index = read_meta("last_embed_end_index", self.user, person)
            if start_index is None:
                return False
        if end_index is None:
            end_index = read_meta("counter", self.user, person)
            if start_index is None:
                return False
        embed_filename = str(self.embed_dir / (person + ".pkl"))
        if os.path.exists(embed_filename):
            try:
                with open(embed_filename, 'rb') as f:
                    embeds = pickle.load(f)
            except EnvironmentError:
                raise DBError("Loading pickle failed!")
        else:
            embeds = [] # each entry is a tuple of 3: array, start index and end index
        embeds.append((embed, start_index, end_index))
        try:
            with open(embed_filename, 'wb') as f:
                pickle.dump(embeds, f)
        except EnvironmentError:
            raise DBError("Dumping pickle failed!")
        write_meta("last_embed_end_index", end_index, self.user, person)
        return True

    def get_all_embeds(self):
        filenames = os.listdir(str(self.embed_dir))
        all_persons = [os.path.splitext(file)[0] for file in filenames]
        all_embeds = {}
        for person in all_persons:
            all_embeds[person] = self.get_embeds(person)
        return all_embeds

    def get_embeds(self, person:str=None):
        '''get all embeds of a person's chatlog
        return vecs: list of numpy arrays, indices: list of int pairs (start, end)'''
        embeds = []
        embed_filename = str(self.embed_dir / (person + ".pkl"))
        if os.path.exists(embed_filename):
            try:
                with open(embed_filename, 'rb') as f:
                    embeds = pickle.load(f)
            except EnvironmentError:
                raise DBError("Loading pickle failed!")
        return embeds

    def clear(self, person):
        filename = str(self.dir / (person + ".json"))
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except EnvironmentError:
                raise DBError("Clearing chatlog failed!")
        write_meta("last_timestamp", None, self.user, person)
        write_meta("counter", 0, self.user, person)
        write_meta("last_embed_end_index", None, self.user, person)

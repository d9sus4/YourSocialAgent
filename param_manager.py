import math
import numpy as np
from typing import *
import os
import pickle
from pathlib import Path
from error import *
from collections import deque, Counter

default_params = [
    "verbosity",
    "seriousness",
    "politeness",
    ]

levels = ["extremely low",
          "very low",
          "low",
          None,
          "high",
          "very high",
          "extremely high",
        ]

NUM_LEVELS = len(levels)
COUNT_WINDOW_SIZE = 5 * NUM_LEVELS

class ParamVector:

    def __init__(self, scope: str, identifier: str):
        self.scope = scope # scope type, contact or context
        self.id = identifier # name
        self.vmax = 1.0
        self.vmin = 0.0
        # legacy
        self.hidden = {}
        for param in default_params:
            self.hidden[param] = 0.5 * (self.vmax + self.vmin)
        self.interest = {}
        # params
        self.params = {}
        for p in default_params:
            self.params[p] = {}
            self.params[p]["value"] = NUM_LEVELS // 2
            self.params[p]["history"] = deque(maxlen=COUNT_WINDOW_SIZE)
    
    def __str__(self):
        v = "Hidden:\n"
        for k in self.hidden.keys():
            v += k + ": " + str(self.hidden[k]) + '\n'
        v += "\nInterest:\n"
        for k in self.interest.keys():
            v += k + ": " + str(self.interest[k]) + '\n'
        return v

    def get_all_param_names(self):
        ''' Return names of all params as a list. '''
        params = []
        params.extend(self.hidden.keys())
        params.extend(self.interest.keys())
        return params
    
    def init_new_param(self, name, value=None):
        self.interest[name] = 0.5 * (self.vmax + self.vmin)

    def higher_param(self, name, value=None):
        if name in self.hidden.keys():
            self.hidden[name] = 0.5 * (self.hidden[name] + self.vmax)
        elif name in self.interest.keys():
            self.interest[name] = 0.5 * (self.interest[name] + self.vmax)

    def lower_param(self, name, value=None):
        if name in self.hidden.keys():
            self.hidden[name] = 0.5 * (self.hidden[name] + self.vmin)
        elif name in self.interest.keys():
            self.interest[name] = 0.5 * (self.interest[name] + self.vmin)

    def sample(self, sigma) -> Union[List, Dict, Dict]:
        ''' Take a sample of parameters.
        Return 3 values: list of constructed natural language phrases describing significant params, hidden dict, interest dict.
        sigma: if sigma is not 0, this function will apply a gaussian noise to every parameter in the list'''
        hidden = self.hidden.copy()
        interest = self.interest.copy()
        all = hidden.copy()
        all.update(interest)
        prompt = []
        for param in all.keys():
            level = levels[int((all[param] - self.vmin) / (self.vmax - self.vmin) / (1.0 / len(levels)))]
            if level is not None:
                prompt.append(level + ' ' + param)

        return prompt, hidden, interest
    

class ParamManager:
    
    def __init__(self):
        self.set_user("default")

    def set_user(self, user):
        self.dir = Path("./data") / user / "param"
        if not os.path.exists(str(self.dir)):
            os.makedirs(str(self.dir))

    def get(self, scope, identifier):
        '''Get a specific vector by scope (contact or context) and identifier.'''
        filename = str(self.dir / (scope + '_' + identifier + ".pkl"))
        if os.path.exists(filename):
            try:
                with open(filename, 'rb') as f:
                    data = pickle.load(f)
            except EnvironmentError:
                raise DBError("Loading pickle failed!")
        else:
            data = ParamVector(scope, identifier)
        return data

    def writeback(self, data: ParamVector):
        dir = str(self.dir / data.scope)
        if not os.path.exists(dir):
            os.makedirs(dir)
        filename = str(self.dir / (data.scope + '_' + data.id + ".pkl"))
        try:
            with open(filename, 'wb') as f:
                pickle.dump(data, f)
        except EnvironmentError:
            raise DBError("Dumping pickle failed!")
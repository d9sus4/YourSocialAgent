import math
import numpy as np
from typing import *
import os
import pickle
from pathlib import Path
from error import *
from collections import deque, Counter
import random

DEFAULT_PARAMS = [
    "verbosity",
    "seriousness",
    "politeness",
    ]

LEVELS = ["extremely low",
          "very low",
          "low",
          None,
          "high",
          "very high",
          "extremely high",
        ]

NUM_LEVELS = len(LEVELS) # [0, 1, ..., NUM_LEVELS-1]
COUNT_WINDOW_SIZE = 5 * NUM_LEVELS
GAUSSIAN_FILTER_SIGMA_UNIT = NUM_LEVELS / 3
COUNT_BIAS = 1

class ParamVector:

    def __init__(self, scope: str, identifier: str):
        self.scope = scope # scope type, contact or context
        self.id = identifier # name
        self.params = {} # {name: value}
        self.history = {} # {name: deque}
        for p in DEFAULT_PARAMS:
            self.params[p] = NUM_LEVELS // 2
            self.history[p] = deque(maxlen=COUNT_WINDOW_SIZE)
    
    def __str__(self):
        v = ""
        for k in self.params.keys():
            v += k + ": " + str(self.params[k]) + '\n'
        return v

    def get_all_param_names(self):
        ''' Return names of all params as a list. '''
        return self.params.keys()
    
    def init_new_param(self, name, value=None):
        self.params[name] = value if value is not None else NUM_LEVELS // 2
        self.history[name] = deque(maxlen=COUNT_WINDOW_SIZE)

    def higher_param(self, name):
        self.params[name] = int((self.params[name] + NUM_LEVELS) / 2)

    def lower_param(self, name, value=None):
        self.params[name] = int(self.params[name] / 2)

    def sample(self, randomness:int=0, k:int=1) -> List[Dict]:
        ''' Take a sample of parameters.
        Return a list of params dicts, num = k.
        randomness: scale of the gaussian filter'''
        def get_gaussian_y(x, mu, sigma):
            y = (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-(x - mu)**2 / (2 * sigma**2))
            return y
        prompt = []
        if randomness == 0:
            return [self.params.copy() for _ in range(k)]
        else:
            result = [{} for _ in range(k)]
            for p in self.params.keys():
                counter = Counter(self.history[p])
                options = range(NUM_LEVELS)
                weights = []
                for v in options:
                    weights.append((counter.get(v, 0) + COUNT_BIAS) * get_gaussian_y(v, mu=self.params[p], sigma=randomness*GAUSSIAN_FILTER_SIGMA_UNIT))
                sample = random.choices(options, weights=weights, k=k)
                for i in range(k):
                    result[i][p] = sample[i]
            return result

        
    def update(self, params:dict):
        for p in params.keys():
            if p in self.params.keys():
                self.params[p] = params[p]
                self.history[p].append(params[p])
    

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
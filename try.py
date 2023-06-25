# l = [1, 2, 3]
# print(l[0:])
# print(l[-2:])
# print(l[-5:])
# print(l[None:None])
# print(l[:-2])

import numpy as np

a = [10, 234, 199, 68, 120]
sorted_indices = np.argsort(a)
b = np.argsort(sorted_indices)

print(b)
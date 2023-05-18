l = [1, 2, 3]
print(l[0:])
print(l[-2:])
print(l[-5:])
print(l[None:None])
from meta import *
write_meta("key", None, "test", "test")
print(type(read_meta("key", "test", "test")))
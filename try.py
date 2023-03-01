l = ["fuck", "ferry", "hello", "feiwu", "fine", "bye"]
for i in range(len(l)-1, -1, -1):
    if l[i][0] == 'f':
        del l[i]
print(l)
print(int("fuck you"))
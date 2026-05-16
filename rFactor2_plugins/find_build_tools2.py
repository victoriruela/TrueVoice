import os
import glob
roots = [
    r'C:\Program Files\Microsoft Visual Studio\2022',
    r'C:\Program Files (x86)\Microsoft Visual Studio\2022',
    r'C:\Program Files\CMake',
    r'C:\Program Files (x86)\CMake',
    r'C:\Program Files',
    r'C:\Program Files (x86)',
]
found = []
print('SEARCH START')
for root in roots:
    if not os.path.isdir(root):
        continue
    for pattern in ['**/cmake.exe', '**/cl.exe', '**/ninja.exe']:
        for path in glob.glob(os.path.join(root, pattern), recursive=True):
            found.append(path)
            if len(found) >= 50:
                break
    if found:
        break
print('FOUND', len(found))
for path in found:
    print(path)

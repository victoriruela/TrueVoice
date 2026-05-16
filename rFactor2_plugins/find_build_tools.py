import os
import sys
import glob
paths = [
    r'C:\Program Files\Microsoft Visual Studio\2022',
    r'C:\Program Files (x86)\Microsoft Visual Studio\2022',
    r'C:\Program Files\CMake',
    r'C:\Program Files (x86)\CMake',
    r'C:\Program Files',
    r'C:\Program Files (x86)',
]
results = []
for root in paths:
    if not os.path.isdir(root):
        continue
    for pattern in ['**/cmake.exe', '**/cl.exe', '**/ninja.exe']:
        results.extend(glob.glob(os.path.join(root, pattern), recursive=True))
    if results:
        break
print('FOUND', len(results))
for path in results[:50]:
    print(path)

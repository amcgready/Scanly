import os
import json

config_path = '/home/adam/Desktop/Scanly/config/monitored_directories.json'

if not os.path.exists(config_path):
    print("No monitored_directories.json found.")
    exit(1)

with open(config_path, 'r') as f:
    data = json.load(f)

changed = False
for dir_id, info in data.items():
    if 'path' not in info or not info['path']:
        print(f"Directory {dir_id} missing path!")
        continue
    if 'name' not in info or not info['name']:
        info['name'] = os.path.basename(info['path'])
        changed = True

if changed:
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=2)
    print("Fixed monitored_directories.json.")
else:
    print("No changes needed.")
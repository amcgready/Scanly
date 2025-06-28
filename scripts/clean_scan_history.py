import os

scan_history_path = '/home/adam/Desktop/Scanly/src/scan_history.txt'
cleaned_lines = []

with open(scan_history_path, 'r') as f:
    for line in f:
        path = line.strip()
        if os.path.isfile(path):
            cleaned_lines.append(path)

with open(scan_history_path, 'w') as f:
    for line in cleaned_lines:
        f.write(line + '\n')

print(f"Cleaned scan_history.txt: {len(cleaned_lines)} file entries kept.")
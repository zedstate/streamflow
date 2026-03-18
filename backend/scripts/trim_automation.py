import sys

path = "backend/automation_config_manager.py"
with open(path, "r") as f:
    lines = f.readlines()

trimmed_lines = []
for i in range(len(lines)-1, -1, -1):
    if "return _automation_config_manager" in lines[i]:
        trimmed_lines = lines[:i+1]
        break

if not trimmed_lines:
    print("Could not find return hook!")
    sys.exit(1)

with open(path, "w") as f:
    f.writelines(trimmed_lines)

print("Trimmed perfectly!")

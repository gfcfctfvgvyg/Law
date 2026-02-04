#!/usr/bin/env python3

with open('/workspace/main.py', 'r') as f:
    lines = f.readlines()

# Find the line with "import config" and insert dotenv before it
new_lines = []
for i, line in enumerate(lines):
    if line.strip() == '# Import configuration' and i > 0 and 'import config' in lines[i+1]:
        # Add dotenv imports before this
        new_lines.append('from dotenv import load_dotenv\n')
        new_lines.append('\n')
        new_lines.append('# Load environment variables from .env file\n')
        new_lines.append('load_dotenv()\n')
        new_lines.append('\n')
    new_lines.append(line)

with open('/workspace/main.py', 'w') as f:
    f.writelines(new_lines)

print("✅ Added dotenv import and load_dotenv() call")

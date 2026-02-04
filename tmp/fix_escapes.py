#!/usr/bin/env python3

with open('/workspace/main.py', 'r') as f:
    lines = f.readlines()

# Find and fix the problematic lines
new_lines = []
for line in lines:
    # Fix the broken print statements
    if 'print("\n📝 Setup Instructions:")' in line:
        line = line.replace('print("\n📝 Setup Instructions:")', 'print("\\n📝 Setup Instructions:")')
    if "print(\"   3. Or set environment variable: export DISCORD_TOKEN='your_token'\n\")" in line:
        line = line.replace("print(\"   3. Or set environment variable: export DISCORD_TOKEN='your_token'\n\")", 
                          "print(\"   3. Or set environment variable: export DISCORD_TOKEN='your_token'\\n\")")
    new_lines.append(line)

with open('/workspace/main.py', 'w') as f:
    f.writelines(new_lines)

print("✅ Fixed escape sequences in main.py")

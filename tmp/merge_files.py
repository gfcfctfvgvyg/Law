#!/usr/bin/env python3
import sys

with open('/workspace/main.py', 'r') as f:
    main_content = f.read()

with open('/workspace/new_features.py', 'r') as f:
    new_features = f.read()

# Find the RUN BOT comment
marker = '\n# ═══════════════════════════════════════════════════════════════════════════════\n# RUN BOT'
pos = main_content.find(marker)

if pos == -1:
    print("ERROR: Could not find RUN BOT marker")
    sys.exit(1)

# Insert the new code before RUN BOT
merged = main_content[:pos] + '\n' + new_features + main_content[pos:]

with open('/workspace/main.py', 'w') as f:
    f.write(merged)

print("✅ Features merged successfully!")

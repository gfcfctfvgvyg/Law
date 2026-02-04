#!/usr/bin/env python3

with open('/workspace/main.py', 'r') as f:
    content = f.read()

# Find and replace the bot.run section
import re

pattern = r'if __name__ == "__main__":\s+TOKEN = os\.getenv\("DISCORD_TOKEN"\)\s+if not TOKEN:\s+print\("DISCORD_TOKEN not found!.*?"\)\s+exit\(1\)\s+bot\.run\(TOKEN\)'

replacement = '''if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN not found!")
        print("\n📝 Setup Instructions:")
        print("   1. Copy .env.example to .env: cp .env.example .env")
        print("   2. Add your bot token to DISCORD_TOKEN in the .env file")
        print("   3. Or set environment variable: export DISCORD_TOKEN='your_token'\\n")
        exit(1)
    
    bot.run(TOKEN)'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('/workspace/main.py', 'w') as f:
    f.write(content)

print("✅ Updated bot.run() section")

import ast
import sys

try:
    with open("bot.py", "r") as f:
        ast.parse(f.read())
    print("✅ bot.py syntax is valid!")
    sys.exit(0)
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    sys.exit(1)

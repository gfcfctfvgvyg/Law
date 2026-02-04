import ast
with open('main.py', 'r') as f:
    ast.parse(f.read())
print('main.py - OK')
with open('config.py', 'r') as f:
    ast.parse(f.read())
print('config.py - OK')
print('All valid!')

import ast
with open('neural_saga.py', encoding='utf-8') as f:
    ast.parse(f.read())
print('OK')

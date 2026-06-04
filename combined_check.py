import ast, sys, os

base = os.path.dirname(os.path.abspath(__file__))
files = sorted(f for f in os.listdir(base) if f.endswith('.py') and f != os.path.basename(__file__))

all_ok = True
for f in files:
    path = os.path.join(base, f)
    try:
        with open(path, encoding='utf-8') as fh:
            ast.parse(fh.read())
        print(f'{f}: OK')
    except SyntaxError as e:
        print(f'{f}: FAIL - {e}')
        all_ok = False

if all_ok:
    print(f'\nALL OK ({len(files)} files)')
else:
    sys.exit(1)

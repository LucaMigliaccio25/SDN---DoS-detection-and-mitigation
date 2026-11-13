#!/usr/bin/env python3
"""Controlli statici sui file consegnati; NON sostituiscono un test su Mininet."""
from pathlib import Path
import ast,json
root=Path(__file__).resolve().parents[1]
for p in (root/'controllers').glob('*.py'):
    ast.parse(p.read_text())
    print('Python OK:',p.relative_to(root))
for p in (root/'topologies').glob('*.py'):
    ast.parse(p.read_text()); print('Python OK:',p.relative_to(root))
for p in (root/'config').glob('*.json'):
    obj=json.loads(p.read_text());assert isinstance(obj,dict)
    print('JSON OK:',p.relative_to(root),len(obj),'entry')

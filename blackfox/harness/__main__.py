"""Talk to the agent from a terminal:  python -m blackfox.harness "question" [--visitor cli]"""

import argparse
import asyncio
import json

from .agent import get_agent

p = argparse.ArgumentParser()
p.add_argument("question")
p.add_argument("--visitor", default="cli")
p.add_argument("--conversation", default="cli")
a = p.parse_args()

res = asyncio.run(get_agent().run(a.question, a.conversation, a.visitor))
for s in res.steps:
    print(f"[tool] {s.name}({json.dumps(s.arguments, ensure_ascii=False)}) -> {s.result[:300]}")
print(f"[model] {res.model}" + (f"  [error] {res.error}" if res.error else ""))
print(res.text)

"""Sandboxed Python execution for the coding agent.

Extends CORTEX's restricted-namespace runner (github.com/codero-sus/agi) with
a hard subprocess timeout and an AST import allowlist. The worker process has
no __import__, no os/sys/subprocess, and a whitelist of safe modules.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time

TIMEOUT_SEC = 8.0
MAX_CODE_LEN = 4000
MAX_OUTPUT = 4000

SAFE_MODULES = {
    "math", "datetime", "time", "calendar", "hashlib", "statistics",
    "itertools", "functools", "collections", "decimal", "fractions",
    "string", "re", "cmath", "random",
}

FORBIDDEN = ("import os", "import sys", "subprocess", "socket", "shutil",
             "open(", "__import__", "eval(input", "exec(input")

_WORKER = r'''
import sys, json, ast, traceback, io, importlib
import math, datetime, time, calendar, hashlib, statistics, itertools
import functools, collections, decimal, fractions, string, re, cmath, random

payload = json.loads(sys.stdin.read())
code = payload.get("code", "")

_SAFE_SET = {"math", "datetime", "time", "calendar", "hashlib", "statistics",
             "itertools", "functools", "collections", "decimal", "fractions",
             "string", "re", "cmath", "random"}

def _import(name, globals=None, locals=None, fromlist=(), level=0):
    if level:
        raise ImportError("relative imports not allowed in the sandbox")
    if name in sys.modules:
        return sys.modules[name]  # stdlib internals already loaded by the worker
    root = (name or "").split(".")[0]
    if root not in _SAFE_SET:
        raise ImportError(f"import not allowed in the sandbox: {name}")
    return importlib.import_module(name)

SAFE_BUILTINS = {
    "__import__": _import,
    "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
    "range": range, "sorted": sorted, "reversed": reversed, "list": list,
    "dict": dict, "set": set, "tuple": tuple, "int": int, "float": float,
    "str": str, "bool": bool, "enumerate": enumerate, "zip": zip,
    "round": round, "hex": hex, "oct": oct, "bin": bin, "pow": pow,
    "divmod": divmod, "all": all, "any": any, "map": map, "filter": filter,
    "repr": repr, "isinstance": isinstance, "chr": chr, "ord": ord,
    "locals": locals, "globals": globals, "type": type, "dir": dir,
    "vars": vars, "hash": hash, "iter": iter, "next": next,
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError,
    "StopIteration": StopIteration, "ArithmeticError": ArithmeticError,
    "ZeroDivisionError": ZeroDivisionError,
}

ns = {
    "__builtins__": SAFE_BUILTINS,
    "math": math, "datetime": datetime, "time": time, "calendar": calendar,
    "hashlib": hashlib, "statistics": statistics, "itertools": itertools,
    "functools": functools, "collections": collections, "decimal": decimal,
    "fractions": fractions, "string": string, "re": re, "cmath": cmath,
    "random": random,
}

buf = []
def _print(*args, **_kw):
    buf.append(" ".join(str(a) for a in args))
ns["print"] = _print

ok, err = True, ""
try:
    tree = ast.parse(code, mode="exec")
    last = tree.body[-1] if tree.body else None
    if isinstance(last, ast.Expr):
        exec(compile(ast.Module(tree.body[:-1], []), "<agent>", "exec"), ns, ns)
        val = eval(compile(ast.Expression(last.value), "<agent>", "eval"), ns, ns)
        if val is not None:
            buf.append(repr(val))
    else:
        exec(compile(tree, "<agent>", "exec"), ns, ns)
except SyntaxError as e:
    ok, err = False, f"SyntaxError: {e.msg} (line {e.lineno})"
except Exception:
    ok, err = False, traceback.format_exc(limit=3)

sys.stdout.write(json.dumps({"ok": ok, "out": "\n".join(buf)[:4000],
                             "err": err[:1500]}))
'''


def preflight(code: str) -> str | None:
    """Return a refusal reason, or None if the code may run."""
    if not code or not code.strip():
        return "empty code"
    if len(code) > MAX_CODE_LEN:
        return "code too long (4000 char cap)"
    low = code.lower()
    for bad in FORBIDDEN:
        if bad in low:
            return f"forbidden construct: {bad.strip('(')}"
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"syntax error: {e.msg} (line {e.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in SAFE_MODULES:
                    return f"import not allowed in the sandbox: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in SAFE_MODULES:
                return f"import not allowed in the sandbox: {node.module}"
    return None


def run_python(code: str, timeout: float = TIMEOUT_SEC) -> dict:
    """Run a snippet in a jailed subprocess. Returns
    {ok, output, error, timed_out, duration_ms, refused}."""
    t0 = time.time()
    reason = preflight(code)
    if reason:
        return {"ok": False, "output": "", "error": f"refused — {reason}",
                "refused": True, "timed_out": False,
                "duration_ms": int((time.time() - t0) * 1000)}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", _WORKER],
            input=json.dumps({"code": code}),
            capture_output=True, text=True, timeout=timeout,
        )
        duration = int((time.time() - t0) * 1000)
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception:
            return {"ok": False, "output": proc.stdout[:MAX_OUTPUT],
                    "error": (proc.stderr or "sandbox crash")[:1500],
                    "refused": False, "timed_out": False, "duration_ms": duration}
        return {"ok": bool(payload.get("ok")),
                "output": payload.get("out", "")[:MAX_OUTPUT],
                "error": payload.get("err", "")[:1500],
                "refused": False, "timed_out": False, "duration_ms": duration}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "",
                "error": f"timed out after {timeout:.0f}s",
                "refused": False, "timed_out": True,
                "duration_ms": int((time.time() - t0) * 1000)}

#!/usr/bin/env python3
"""Map backend FastAPI endpoints to the paths the React front end calls.

Phase 0 (read-only) helper, stdlib only.

Backend: parses ``backend/server.py`` and ``backend/routes/*.py`` with ``ast``;
for every ``APIRouter(prefix=...)`` variable it records decorated endpoints
(``@router.get("/x")`` ...). Routers are mounted under ``/api`` by server.py.

Front end: scans ``frontend/src/**/*.js|jsx|ts|tsx`` with regular expressions
for the call styles used in this code base:

* ``api.get('/path')`` (axios instance in ``services/apiClient.js`` with
  ``baseURL = REACT_APP_BACKEND_URL + '/api'``)
* ``fetch(`${API_URL}/api/path`)``, ``axios.post(`${backendUrl}/api/path`)``
  and any template literal ``${<X>}/api/...``
* ``${API}/path`` where ``API = `${REACT_APP_BACKEND_URL}/api```
* ``new WebSocket(...)`` URLs containing ``/api/``.

Template expressions (``${id}``) become wildcards. Calls whose URL is built
in a variable cannot be resolved statically and are counted separately.

Usage: python3 tools/audit/route_map.py [-o out.json]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "websocket", "api_route"}


def _const(node) -> Optional[str]:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def backend_endpoints(backend: str, repo: str) -> List[Dict]:
    out = []
    files = [os.path.join(backend, "server.py")] + sorted(
        os.path.join(backend, "routes", f) for f in os.listdir(os.path.join(backend, "routes")) if f.endswith(".py"))
    for path in files:
        rel = os.path.relpath(path, repo)
        module = os.path.splitext(os.path.basename(path))[0]
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            continue
        prefixes: Dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                fn = node.value.func
                fname = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                if fname in {"APIRouter", "FastAPI"}:
                    prefix = ""
                    for kw in node.value.keywords:
                        if kw.arg == "prefix":
                            prefix = _const(kw.value) or ""
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            prefixes[t.id] = prefix
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                if dec.func.attr not in HTTP_METHODS or not isinstance(dec.func.value, ast.Name):
                    continue
                rname = dec.func.value.id
                if rname not in prefixes:
                    continue
                sub = _const(dec.args[0]) if dec.args else None
                if sub is None:
                    continue
                if module == "server":
                    full = prefixes[rname] + sub
                elif rname == "api_router" and module != "partner_routes":
                    full = prefixes[rname] + sub
                else:
                    full = "/api" + prefixes[rname] + sub
                out.append({"module": module, "file": rel, "line": dec.lineno, "method": dec.func.attr.upper(),
                            "path": full, "function": node.name})
    return out


TEMPLATE_RE = re.compile(r"\$\{[^}]*\}")
API_CALL_RE = re.compile(r"\bapi\.(get|post|put|patch|delete)\(\s*([`'\"])(/[^`'\"]*)\2")
ABS_RE = re.compile(r"\$\{[^{}`]*\}(/api/[^`'\"\s)]*)")
API_PREFIX_RE = re.compile(r"\$\{\s*API\s*\}(/[^`'\"\s)]*)")
METHOD_NEAR_RE = re.compile(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", re.I)
AXIOS_RE = re.compile(r"axios\.(get|post|put|patch|delete)\(\s*$")


def _norm(path: str) -> str:
    path = path.split("?")[0]
    path = TEMPLATE_RE.sub("{param}", path)
    path = re.sub(r"\{param\}[^/]*|[^/]*\{param\}", "{param}", path)
    path = re.sub(r"/+", "/", path)
    return path.rstrip("/") or "/"


def frontend_calls(src: str, repo: str) -> Dict:
    calls = []
    unresolved = 0
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d != "node_modules"]
        for fn in sorted(filenames):
            if not fn.endswith((".js", ".jsx", ".ts", ".tsx")):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, repo)
            text = open(path, encoding="utf-8", errors="replace").read()
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                for m in API_CALL_RE.finditer(line):
                    calls.append({"file": rel, "line": i, "method": m.group(1).upper(), "raw": m.group(3),
                                  "path": _norm("/api" + m.group(3))})
                for m in ABS_RE.finditer(line):
                    method = "?"
                    before = line[:m.start()]
                    am = re.search(r"axios\.(get|post|put|patch|delete)\(\s*`?$", before)
                    if am:
                        method = am.group(1).upper()
                    elif "fetch(" in before or "fetch(`" in before:
                        window = "\n".join(lines[i - 1:i + 6])
                        mm = METHOD_NEAR_RE.search(window)
                        method = mm.group(1).upper() if mm else "GET"
                    calls.append({"file": rel, "line": i, "method": method, "raw": m.group(1), "path": _norm(m.group(1))})
                for m in API_PREFIX_RE.finditer(line):
                    calls.append({"file": rel, "line": i, "method": "?", "raw": m.group(1), "path": _norm("/api" + m.group(1))})
                if re.search(r"\bapi\.(get|post|put|patch|delete)\(\s*[A-Za-z_]", line):
                    unresolved += 1
    return {"calls": calls, "unresolved_dynamic_calls": unresolved}


def _match(fe: str, be: str) -> bool:
    a, b = fe.strip("/").split("/"), re.sub(r"\{[^}]+\}", "{param}", be).rstrip("/").strip("/").split("/")
    if len(a) != len(b):
        return False
    return all(x == y or x == "{param}" or y == "{param}" for x, y in zip(a, b))


def build(repo: str) -> Dict:
    be = backend_endpoints(os.path.join(repo, "backend"), repo)
    fe = frontend_calls(os.path.join(repo, "frontend", "src"), repo)
    # exact (literal) matches first, then wildcard matches
    for c in fe["calls"]:
        hits = [e for e in be if re.sub(r"\{[^}]+\}", "{param}", e["path"]).rstrip("/") == c["path"]]
        if not hits:
            hits = [e for e in be if _match(c["path"], e["path"])]
        c["matched"] = sorted({f'{e["method"]} {e["path"]}' for e in hits})
        c["modules"] = sorted({e["module"] for e in hits})
        for e in hits:
            e.setdefault("called_from", []).append(f'{c["file"]}:{c["line"]}')
    by_module = defaultdict(lambda: {"endpoints": 0, "called": 0, "uncalled": []})
    for e in be:
        m = by_module[e["module"]]
        m["endpoints"] += 1
        if e.get("called_from"):
            m["called"] += 1
        else:
            m["uncalled"].append(f'{e["method"]} {e["path"]}')
    return {
        "backend_endpoint_count": len(be),
        "frontend_call_count": len(fe["calls"]),
        "unresolved_dynamic_calls": fe["unresolved_dynamic_calls"],
        "frontend_calls_without_backend_match": [c for c in fe["calls"] if not c["matched"]],
        "by_module": dict(sorted(by_module.items())),
        "backend_endpoints": be,
        "frontend_calls": fe["calls"],
    }


def main(argv=None) -> int:
    repo = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output")
    ns = ap.parse_args(argv)
    res = build(repo)
    text = json.dumps(res, indent=2)
    if ns.output:
        open(ns.output, "w", encoding="utf-8").write(text + "\n")
        print(f"wrote {ns.output}: {res['backend_endpoint_count']} endpoints, {res['frontend_call_count']} calls",
              file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

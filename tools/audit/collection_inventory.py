#!/usr/bin/env python3
"""Static MongoDB collection inventory for the AirYatra backend.

Phase 0 (read-only) audit helper. Walks ``backend/**/*.py`` with the stdlib
``ast`` module (no imports of project code, no DB access) and reports:

* every collection name accessed (``db.<name>.``, ``db["name"]``,
  ``db.get_collection("name")``, ``database.<name>``, aliases such as
  ``coll = db.bookings`` / ``self.collection = db.audit_logs``, variables
  obtained from ``get_database()`` / ``Depends(get_database)`` and
  ``$lookup.from`` targets in aggregation pipelines);
* the files and lines referencing each collection and operation counts;
* field names seen in insert dict literals, filter keys, ``$set`` (and other
  update-operator) keys, sort keys, with inferred value kinds
  (ISO string vs ``datetime``, UUID string, float, int, ...) and string
  constants (enum candidates);
* every ``create_index`` / ``create_indexes`` call (collection, keys, options);
* dynamic collection accesses (``db[var]``) that could not be resolved;
* query inputs that look like raw client data (NoSQL injection candidates);
* Pydantic ``BaseModel`` classes and their fields (for joining with
  ``insert_one(model.dict())`` hints).

Usage::

    python3 tools/audit/collection_inventory.py [--root backend] [-o out.json]

Files that fail to parse are skipped and listed under ``parse_errors``.
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set

# Names that are always treated as a database handle.
ROOT_NAMES = {"db", "database", "_db", "mongo_db", "mongodb", "motor_db"}
ROOT_SELF_ATTRS = {"db", "_db", "database", "mongo_db"}
# Calls whose result is a database handle.
DB_FACTORY_FUNCS = {"get_database", "get_database_sync", "get_db", "_get_db", "get_mongo_db"}

# Attributes of a database handle that are not collections.
NON_COLLECTION_ATTRS = {
    "client", "command", "list_collection_names", "list_collections", "get_collection",
    "create_collection", "drop_collection", "name", "with_options", "admin", "watch",
    "aggregate", "codec_options", "read_preference", "write_concern", "read_concern",
    "validate_collection", "dereference", "cursor_command", "get_database",
    "get_database_sync", "connect_to_mongo", "close_mongo_connection", "db",
    "MONGO_OPTIONS", "logger", "Database", "AsyncIOMotorClient", "logging",
}

COLLECTION_METHODS = {
    "find", "find_one", "insert_one", "insert_many", "update_one", "update_many",
    "replace_one", "delete_one", "delete_many", "count_documents",
    "estimated_document_count", "aggregate", "distinct", "find_one_and_update",
    "find_one_and_delete", "find_one_and_replace", "create_index", "create_indexes",
    "bulk_write", "drop", "index_information", "list_indexes", "drop_index",
    "drop_indexes", "watch", "rename", "find_raw_batches",
}
FILTER_METHODS = {
    "find", "find_one", "update_one", "update_many", "replace_one", "delete_one",
    "delete_many", "count_documents", "distinct", "find_one_and_update",
    "find_one_and_delete", "find_one_and_replace",
}
UPDATE_METHODS = {"update_one", "update_many", "find_one_and_update"}
INSERT_METHODS = {"insert_one", "insert_many", "replace_one", "find_one_and_replace"}
ENUM_SAMPLE_MAX_LEN = 48
ENUM_SAMPLES_PER_FIELD = 25


# --------------------------------------------------------------------------- helpers

def _unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - defensive
        return "<unparseable>"


def _const_str(node: Optional[ast.AST]) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _dotted(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append(_dotted(node.func) + "()")
    else:
        parts.append("?")
    return ".".join(reversed(parts))


class Scope:
    """Assignments visible inside one function (or the module)."""

    def __init__(self, node: ast.AST, parent: Optional["Scope"] = None):
        self.node = node
        self.parent = parent
        self.dict_assigns: Dict[str, List[ast.AST]] = defaultdict(list)
        self.subscript_keys: Dict[str, List[ast.Subscript]] = defaultdict(list)
        self.simple_assigns: Dict[str, List[ast.AST]] = defaultdict(list)
        self.db_roots: Set[str] = set()
        self.aliases: Dict[str, str] = {}
        self.params: Dict[str, str] = {}  # name -> annotation text

    def lookup(self, attr: str, name: str):
        s: Optional[Scope] = self
        while s is not None:
            v = getattr(s, attr)
            if name in v and v[name]:
                return v[name]
            s = s.parent
        return None

    def is_root(self, name: str) -> bool:
        s: Optional[Scope] = self
        while s is not None:
            if name in s.db_roots:
                return True
            s = s.parent
        return name in ROOT_NAMES


def _iter_scope_nodes(node: ast.AST) -> Iterable[ast.AST]:
    """Walk ``node`` without descending into nested function/class bodies."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(n))


def _is_db_factory(value: ast.AST) -> bool:
    if isinstance(value, ast.Await):
        value = value.value
    if isinstance(value, ast.Call):
        name = _call_name(value)
        if name in DB_FACTORY_FUNCS:
            return True
        if name == "Depends" and value.args and isinstance(value.args[0], (ast.Name, ast.Attribute)):
            dep = value.args[0].id if isinstance(value.args[0], ast.Name) else value.args[0].attr
            return dep in DB_FACTORY_FUNCS
    if isinstance(value, ast.Subscript):
        # client[db_name] / self.client[name] / db.client[settings.db_name]
        base = value.value
        base_name = base.id if isinstance(base, ast.Name) else (base.attr if isinstance(base, ast.Attribute) else "")
        return base_name in {"client", "c", "mongo_client", "motor_client", "_client"}
    return False


# --------------------------------------------------------------------------- analyser

class Inventory:
    def __init__(self) -> None:
        self.collections: Dict[str, Dict[str, Any]] = {}
        self.indexes: List[Dict[str, Any]] = []
        self.dynamic: List[Dict[str, Any]] = []
        self.suspicious: List[Dict[str, Any]] = []
        self.models: Dict[str, Dict[str, Any]] = {}
        self.parse_errors: List[Dict[str, str]] = []
        self.files_scanned = 0

    def coll(self, name: str) -> Dict[str, Any]:
        c = self.collections.get(name)
        if c is None:
            c = {
                "references": 0,
                "files": defaultdict(set),
                "operations": Counter(),
                "fields": defaultdict(lambda: {"sources": Counter(), "kinds": Counter(), "samples": set()}),
                "filter_keys": Counter(),
                "set_keys": Counter(),
                "update_operators": Counter(),
                "sort_keys": Counter(),
                "insert_model_hints": Counter(),
                "unresolved_inserts": 0,
                "indexes": [],
            }
            self.collections[name] = c
        return c

    # -------------------------------------------------------------- output
    def to_json(self, root: str) -> Dict[str, Any]:
        out_colls = {}
        for name in sorted(self.collections):
            c = self.collections[name]
            fields = {}
            for f in sorted(c["fields"]):
                d = c["fields"][f]
                fields[f] = {
                    "sources": dict(d["sources"]),
                    "kinds": dict(d["kinds"]),
                    "samples": sorted(d["samples"])[:ENUM_SAMPLES_PER_FIELD],
                }
            out_colls[name] = {
                "references": c["references"],
                "files": {k: sorted(v) for k, v in sorted(c["files"].items())},
                "operations": dict(c["operations"]),
                "fields": fields,
                "filter_keys": dict(c["filter_keys"].most_common()),
                "set_keys": dict(c["set_keys"].most_common()),
                "update_operators": dict(c["update_operators"].most_common()),
                "sort_keys": dict(c["sort_keys"].most_common()),
                "insert_model_hints": dict(c["insert_model_hints"]),
                "unresolved_inserts": c["unresolved_inserts"],
                "indexes": c["indexes"],
            }
        return {
            "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
            "root": root,
            "files_scanned": self.files_scanned,
            "parse_errors": self.parse_errors,
            "collection_count": len(out_colls),
            "collections": out_colls,
            "indexes": self.indexes,
            "dynamic_accesses": self.dynamic,
            "suspicious_query_inputs": self.suspicious,
            "pydantic_models": self.models,
        }


class FileAnalyser:
    def __init__(self, inv: Inventory, rel: str, tree: ast.Module):
        self.inv = inv
        self.rel = rel
        self.tree = tree
        self.scope_of: Dict[int, Scope] = {}
        self.class_aliases: Dict[str, str] = {}  # self.<attr> -> collection
        self.class_db_attrs: Set[str] = set(ROOT_SELF_ATTRS)
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child._parent = node  # type: ignore[attr-defined]

    # -------------------------------------------------------------- scopes
    def build_scopes(self) -> None:
        mod = Scope(self.tree)
        self._fill_scope(mod, self.tree)
        self.scope_of[id(self.tree)] = mod
        self._build_children(self.tree, mod)

    def _build_children(self, node: ast.AST, scope: Scope) -> None:
        for n in _iter_scope_nodes(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                s = Scope(n, scope)
                self._fill_params(s, n)
                self._fill_scope(s, n)
                self.scope_of[id(n)] = s
                self._build_children(n, s)
            elif isinstance(n, ast.ClassDef):
                self._build_children(n, scope)

    def _fill_params(self, s: Scope, fn: ast.AST) -> None:
        args = fn.args  # type: ignore[attr-defined]
        all_args = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
        defaults = [None] * (len(args.posonlyargs) + len(args.args) - len(args.defaults)) + list(args.defaults)
        defaults += list(args.kw_defaults)
        for a, d in zip(all_args, defaults):
            s.params[a.arg] = _unparse(a.annotation)
            if a.arg in ROOT_NAMES or (d is not None and _is_db_factory(d)):
                s.db_roots.add(a.arg)

    def _fill_scope(self, s: Scope, node: ast.AST) -> None:
        for n in _iter_scope_nodes(node):
            targets: List[ast.AST] = []
            value = None
            if isinstance(n, ast.Assign):
                targets, value = n.targets, n.value
            elif isinstance(n, ast.AnnAssign) and n.value is not None:
                targets, value = [n.target], n.value
            if value is None:
                continue
            for t in targets:
                if isinstance(t, ast.Name):
                    s.simple_assigns[t.id].append(value)
                    if isinstance(value, ast.Dict):
                        s.dict_assigns[t.id].append(value)
                    if _is_db_factory(value):
                        s.db_roots.add(t.id)
                elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    s.subscript_keys[t.value.id].append(t)
                elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                    if _is_db_factory(value):
                        self.class_db_attrs.add(t.attr)

    def scope_for(self, node: ast.AST) -> Scope:
        p = node
        while p is not None:
            if id(p) in self.scope_of:
                return self.scope_of[id(p)]
            p = getattr(p, "_parent", None)
        return self.scope_of[id(self.tree)]

    # -------------------------------------------------------------- root detection
    def _is_root_expr(self, node: ast.AST, scope: Scope) -> bool:
        if isinstance(node, ast.Name):
            return scope.is_root(node.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
            return node.attr in self.class_db_attrs
        if isinstance(node, ast.Call):
            return _call_name(node) in DB_FACTORY_FUNCS
        if isinstance(node, ast.Await):
            return self._is_root_expr(node.value, scope)
        return False

    def collection_of(self, node: ast.AST, scope: Scope) -> Optional[str]:
        """Return the collection name if ``node`` evaluates to a collection."""
        if isinstance(node, ast.Attribute):
            if node.attr not in NON_COLLECTION_ATTRS and not node.attr.startswith("__") \
                    and self._is_root_expr(node.value, scope):
                return node.attr
            if isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in self.class_aliases:
                return self.class_aliases[node.attr]
            return None
        if isinstance(node, ast.Subscript) and self._is_root_expr(node.value, scope):
            key = node.slice
            s = _const_str(key)
            if s is not None:
                return s
            return None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get_collection" and self._is_root_expr(node.func.value, scope):
            return _const_str(node.args[0]) if node.args else None
        if isinstance(node, ast.Name):
            s: Optional[Scope] = scope
            while s is not None:
                if node.id in s.aliases:
                    return s.aliases[node.id]
                s = s.parent
        return None

    # -------------------------------------------------------------- main pass
    def run(self) -> None:
        self.build_scopes()
        # pass 1: aliases (coll = db.x ; self.coll = db.x)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                scope = self.scope_for(node)
                cname = self.collection_of(node.value, scope)
                if cname is None:
                    continue
                t = node.targets[0]
                if isinstance(t, ast.Name):
                    scope.aliases[t.id] = cname
                elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                    self.class_aliases[t.attr] = cname
        # pass 2: usages
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Subscript):
                self._check_dynamic(node)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in COLLECTION_METHODS:
                    scope = self.scope_for(node)
                    cname = self.collection_of(node.func.value, scope)
                    if cname is not None:
                        self._record_call(cname, node, scope)
                if node.func.attr == "sort":
                    self._record_sort(node)
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                scope = self.scope_for(node)
                cname = self.collection_of(node.value, scope)
                if cname is not None:
                    self._ref(cname, node.lineno, "alias")

    def _ref(self, cname: str, line: int, op: str) -> Dict[str, Any]:
        c = self.inv.coll(cname)
        c["references"] += 1
        c["files"][self.rel].add(line)
        c["operations"][op] += 1
        return c

    def _check_dynamic(self, node: ast.Subscript) -> None:
        scope = self.scope_for(node)
        if not self._is_root_expr(node.value, scope):
            return
        if _const_str(node.slice) is not None:
            return
        resolved = None
        if isinstance(node.slice, ast.Name):
            vals = scope.lookup("simple_assigns", node.slice.id) or []
            strs = [_const_str(v) for v in vals if _const_str(v) is not None]
            resolved = strs or None
        self.inv.dynamic.append({
            "file": self.rel, "line": node.lineno, "expr": _unparse(node), "resolved": resolved,
        })
        if resolved:
            for r in resolved:
                self._ref(r, node.lineno, "dynamic")

    # -------------------------------------------------------------- value kinds
    def classify(self, node: Optional[ast.AST], scope: Scope, depth: int = 0) -> List[str]:
        if node is None:
            return ["unknown"]
        if isinstance(node, ast.Await):
            return self.classify(node.value, scope, depth)
        if isinstance(node, ast.Constant):
            v = node.value
            if v is None:
                return ["null"]
            if isinstance(v, bool):
                return ["bool"]
            if isinstance(v, int):
                return ["int"]
            if isinstance(v, float):
                return ["float"]
            if isinstance(v, str):
                return ["str"]
            return [type(v).__name__]
        if isinstance(node, ast.JoinedStr):
            return ["str"]
        if isinstance(node, (ast.Dict, ast.DictComp)):
            return ["object"]
        if isinstance(node, (ast.List, ast.ListComp, ast.Tuple, ast.Set)):
            return ["array"]
        if isinstance(node, ast.IfExp):
            return sorted(set(self.classify(node.body, scope, depth) + self.classify(node.orelse, scope, depth)))
        if isinstance(node, ast.BoolOp):
            out: Set[str] = set()
            for v in node.values:
                out.update(self.classify(v, scope, depth))
            return sorted(out)
        if isinstance(node, ast.BinOp):
            txt = _unparse(node)
            if "timedelta" in txt and ("utcnow" in txt or "now(" in txt):
                return ["datetime"]
            if isinstance(node.op, ast.Div):
                return ["float"]
            if isinstance(node.op, ast.Add) and (isinstance(node.left, (ast.Constant, ast.JoinedStr)) and isinstance(getattr(node.left, "value", None), str)):
                return ["str"]
            if isinstance(node.op, ast.Mod) and _const_str(node.left) is not None:
                return ["str"]
            return ["number"]
        if isinstance(node, ast.UnaryOp):
            return self.classify(node.operand, scope, depth)
        if isinstance(node, ast.Compare):
            return ["bool"]
        if isinstance(node, ast.Call):
            name = _call_name(node)
            dotted = _dotted(node.func)
            if name == "isoformat":
                return ["iso_string"]
            if name == "strftime":
                return ["formatted_date_string"]
            if name in {"utcnow", "now", "today", "fromisoformat", "strptime", "fromtimestamp", "utcfromtimestamp", "combine"} and ("datetime" in dotted or "date" in dotted):
                return ["date" if dotted.endswith("date.today") else "datetime"]
            if name == "str" and node.args:
                inner = _unparse(node.args[0])
                if "uuid" in inner:
                    return ["uuid_string"]
                if "ObjectId" in inner:
                    return ["objectid_string"]
                return ["str"]
            if name in {"uuid4", "uuid1"}:
                return ["uuid_object"]
            if name == "ObjectId":
                return ["objectid"]
            if name == "float":
                return ["float"]
            if name in {"int", "len"}:
                return ["int"]
            if name == "round":
                return ["float" if len(node.args) > 1 else "int"]
            if name in {"bool", "any", "all"}:
                return ["bool"]
            if name in {"sum", "max", "min", "abs"}:
                return ["number"]
            if name in {"dict", "model_dump", "to_dict"}:
                return ["object"]
            if name in {"list", "sorted"}:
                return ["array"]
            if name in {"upper", "lower", "strip", "format", "join", "hexdigest", "hex", "encode", "decode", "title", "replace", "get_secret_value", "token_urlsafe", "token_hex"}:
                return ["str"]
            if name in {"hash_password", "get_password_hash", "hashpw"}:
                return ["password_hash"]
            if name in {"encrypt", "encrypt_data", "encrypt_field"}:
                return ["encrypted"]
            return ["call:" + name]
        if isinstance(node, ast.Attribute):
            if node.attr in {"hex"}:
                return ["str"]
            if node.attr == "value":
                return ["enum_value"]
            return ["expr"]
        if isinstance(node, ast.Name):
            if depth < 2:
                vals = scope.lookup("simple_assigns", node.id)
                if vals:
                    out = set()
                    for v in vals[-3:]:
                        out.update(self.classify(v, scope, depth + 1))
                    return sorted(out)
                ann = scope.params.get(node.id) if node.id in scope.params else None
                if ann:
                    return ["param:" + ann]
            return ["expr"]
        if isinstance(node, ast.Subscript):
            return ["expr"]
        return ["expr"]

    def _const_samples(self, node: ast.AST) -> Set[str]:
        out: Set[str] = set()
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and 0 < len(node.value) <= ENUM_SAMPLE_MAX_LEN:
            out.add(node.value)
        elif isinstance(node, ast.IfExp):
            out |= self._const_samples(node.body) | self._const_samples(node.orelse)
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for e in node.elts:
                out |= self._const_samples(e)
        elif isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                ks = _const_str(k)
                if ks in {"$in", "$nin", "$eq", "$ne"}:
                    out |= self._const_samples(v)
        elif isinstance(node, ast.Attribute) and node.attr.isupper():
            out.add("ENUM:" + _unparse(node))
        return out

    def _field(self, c: Dict[str, Any], key: str, source: str, value: Optional[ast.AST], scope: Scope) -> None:
        f = c["fields"][key]
        f["sources"][source] += 1
        if value is not None:
            if source in {"insert", "set", "setOnInsert"}:
                for k in self.classify(value, scope):
                    f["kinds"][k] += 1
            f["samples"].update(self._const_samples(value))

    # -------------------------------------------------------------- dict resolution
    def resolve_dict_items(self, node: ast.AST, scope: Scope, depth: int = 0) -> Optional[List[tuple]]:
        """Return [(key, value_node)] for a dict literal or a name bound to one."""
        if depth > 3:
            return None
        if isinstance(node, ast.Dict):
            items = []
            for k, v in zip(node.keys, node.values):
                if k is None:  # **spread
                    sub = self.resolve_dict_items(v, scope, depth + 1)
                    if sub:
                        items.extend(sub)
                    continue
                ks = _const_str(k)
                if ks is not None:
                    items.append((ks, v))
            return items
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in {"copy", "deepcopy"} and not node.args:
            return self.resolve_dict_items(node.func.value, scope, depth + 1)
        if isinstance(node, ast.Call) and _call_name(node) in {"dict", "deepcopy"} and isinstance(node.func, ast.Name):
            items = []
            if node.args:
                items = self.resolve_dict_items(node.args[0], scope, depth + 1) or []
            items += [(kw.arg, kw.value) for kw in node.keywords if kw.arg]
            return items or None
        if isinstance(node, ast.Name):
            dicts = scope.lookup("dict_assigns", node.id)
            subs = scope.lookup("subscript_keys", node.id) or []
            if not dicts and not subs:
                return None
            items = []
            for d in dicts or []:
                items.extend(self.resolve_dict_items(d, scope, depth + 1) or [])
            for s in subs:
                ks = _const_str(s.slice)
                if ks is not None:
                    parent = getattr(s, "_parent", None)
                    val = parent.value if isinstance(parent, (ast.Assign, ast.AnnAssign)) else None
                    items.append((ks, val))
            return items
        return None

    def _model_hint(self, node: ast.AST, scope: Scope) -> Optional[str]:
        # booking.dict() / booking.model_dump() / Booking(**x).dict()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"dict", "model_dump"}:
            target = node.func.value
            if isinstance(target, ast.Call):
                return _call_name(target)
            if isinstance(target, ast.Name):
                vals = scope.lookup("simple_assigns", target.id) or []
                for v in reversed(vals):
                    if isinstance(v, ast.Call):
                        n = _call_name(v)
                        if n and n[0].isupper():
                            return n
                ann = scope.params.get(target.id)
                if ann:
                    return ann
        if isinstance(node, ast.Name):
            vals = scope.lookup("simple_assigns", node.id) or []
            for v in reversed(vals):
                h = self._model_hint(v, scope)
                if h:
                    return h
        return None

    def _raw_input_reason(self, node: ast.AST, scope: Scope) -> Optional[str]:
        """Heuristic: does ``node`` look like an unvalidated client dict?"""
        if isinstance(node, ast.Name):
            ann = scope.params.get(node.id)
            if ann is not None and ann.split("[")[0] in {"dict", "Dict", "Any", "typing.Dict"}:
                return f"parameter `{node.id}: {ann}` passed directly"
            vals = scope.lookup("simple_assigns", node.id) or []
            for v in vals:
                txt = _unparse(v)
                if "request.json()" in txt or "await request.json" in txt or "request.query_params" in txt:
                    return f"`{node.id}` comes from `{txt[:60]}`"
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if k is None:
                    r = self._raw_input_reason(v, scope)
                    if r:
                        return "spread " + r
        return None

    # -------------------------------------------------------------- recording
    def _record_call(self, cname: str, call: ast.Call, scope: Scope) -> None:
        method = call.func.attr  # type: ignore[union-attr]
        c = self._ref(cname, call.lineno, method)
        args = list(call.args)
        kw = {k.arg: k.value for k in call.keywords if k.arg}

        if method in FILTER_METHODS:
            flt = args[0] if args else kw.get("filter")
            if flt is not None:
                self._record_filter(c, flt, scope)
                reason = self._raw_input_reason(flt, scope)
                if reason:
                    self.inv.suspicious.append({"file": self.rel, "line": call.lineno, "collection": cname,
                                                "method": method, "kind": "filter", "reason": reason})
            if "sort" in kw:
                self._record_sort_arg(c, kw["sort"])

        if method in UPDATE_METHODS:
            upd = args[1] if len(args) > 1 else kw.get("update")
            if upd is not None:
                items = self.resolve_dict_items(upd, scope)
                if items is None:
                    reason = self._raw_input_reason(upd, scope)
                    if reason:
                        self.inv.suspicious.append({"file": self.rel, "line": call.lineno, "collection": cname,
                                                    "method": method, "kind": "update", "reason": reason})
                for op, val in items or []:
                    if not op.startswith("$"):
                        continue
                    c["update_operators"][op] += 1
                    sub = self.resolve_dict_items(val, scope) if val is not None else None
                    if sub is None and val is not None and op == "$set":
                        hint = self._model_hint(val, scope)
                        if hint:
                            c["insert_model_hints"][hint + " ($set)"] += 1
                    if val is not None and op in {"$set", "$setOnInsert", "$push"}:
                        reason = self._raw_input_reason(val, scope)
                        if reason:
                            self.inv.suspicious.append({"file": self.rel, "line": call.lineno, "collection": cname,
                                                        "method": method, "kind": "$set", "reason": reason})
                    for k, v in sub or []:
                        if op == "$set":
                            c["set_keys"][k] += 1
                            self._field(c, k, "set", v, scope)
                        elif op == "$setOnInsert":
                            self._field(c, k, "setOnInsert", v, scope)
                        else:
                            self._field(c, k, op.lstrip("$"), None, scope)

        if method in INSERT_METHODS:
            if method == "insert_one":
                doc = args[0] if args else kw.get("document")
                docs = [doc] if doc is not None else []
            elif method == "insert_many":
                lst = args[0] if args else kw.get("documents")
                if isinstance(lst, (ast.List, ast.Tuple)):
                    docs = list(lst.elts)
                elif isinstance(lst, ast.ListComp):
                    docs = [lst.elt]
                else:
                    docs = [lst] if lst is not None else []
            else:  # replace_one / find_one_and_replace
                docs = [args[1]] if len(args) > 1 else ([kw["replacement"]] if "replacement" in kw else [])
            for d in docs:
                items = self.resolve_dict_items(d, scope)
                base = d
                while isinstance(base, ast.Call) and (
                        (isinstance(base.func, ast.Attribute) and base.func.attr in {"copy", "deepcopy"} and not base.args)
                        or (isinstance(base.func, ast.Name) and base.func.id in {"dict", "deepcopy"} and base.args)):
                    base = base.func.value if isinstance(base.func, ast.Attribute) else base.args[0]
                hint = self._model_hint(base, scope)
                if hint:
                    c["insert_model_hints"][hint] += 1
                reason = self._raw_input_reason(base, scope)
                if reason:
                    self.inv.suspicious.append({"file": self.rel, "line": call.lineno, "collection": cname,
                                                "method": method, "kind": "insert", "reason": reason})
                for k, v in items or []:
                    self._field(c, k, "insert", v, scope)
                if not items and not hint:
                    c["unresolved_inserts"] += 1

        if method == "aggregate":
            pipe = args[0] if args else kw.get("pipeline")
            if isinstance(pipe, ast.Name):
                vals = scope.lookup("simple_assigns", pipe.id) or []
                pipe = next((v for v in vals if isinstance(v, ast.List)), pipe)
            if isinstance(pipe, ast.List):
                for stage in pipe.elts:
                    for op, val in self.resolve_dict_items(stage, scope) or []:
                        c["update_operators"]["agg:" + op] += 1
                        if op == "$match" and val is not None:
                            self._record_filter(c, val, scope)
                        elif op == "$sort" and val is not None:
                            for k, _ in self.resolve_dict_items(val, scope) or []:
                                c["sort_keys"][k] += 1
                        elif op == "$lookup" and val is not None:
                            for k, v in self.resolve_dict_items(val, scope) or []:
                                if k == "from" and _const_str(v):
                                    self._ref(_const_str(v), call.lineno, "lookup_from")

        if method in {"create_index", "create_indexes"}:
            self._record_index(cname, c, call)

    def _record_filter(self, c: Dict[str, Any], flt: ast.AST, scope: Scope, depth: int = 0) -> None:
        if depth > 4:
            return
        items = self.resolve_dict_items(flt, scope)
        for k, v in items or []:
            if k in {"$or", "$and", "$nor"} and isinstance(v, (ast.List, ast.Tuple)):
                for e in v.elts:
                    self._record_filter(c, e, scope, depth + 1)
                continue
            if k.startswith("$"):
                continue
            c["filter_keys"][k] += 1
            self._field(c, k, "filter", v, scope)

    def _record_sort_arg(self, c: Dict[str, Any], arg: ast.AST) -> None:
        s = _const_str(arg)
        if s is not None:
            c["sort_keys"][s] += 1
        elif isinstance(arg, (ast.List, ast.Tuple)):
            for e in arg.elts:
                if isinstance(e, ast.Tuple) and e.elts and _const_str(e.elts[0]):
                    c["sort_keys"][_const_str(e.elts[0])] += 1
                elif _const_str(e):
                    c["sort_keys"][_const_str(e)] += 1

    def _record_sort(self, call: ast.Call) -> None:
        # walk the receiver chain: db.x.find(...).skip().limit().sort(...)
        node = call.func.value  # type: ignore[union-attr]
        scope = self.scope_for(call)
        while True:
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"find", "aggregate"}:
                    cname = self.collection_of(node.func.value, scope)
                    if cname is None:
                        return
                    c = self.inv.coll(cname)
                    if call.args:
                        self._record_sort_arg(c, call.args[0])
                    first = call.args[0] if call.args else None
                    keys = [_const_str(first)] if _const_str(first) else [
                        _const_str(e.elts[0]) for e in getattr(first, "elts", []) or []
                        if isinstance(e, ast.Tuple) and e.elts and _const_str(e.elts[0])]
                    for k in keys:
                        c["fields"][k]["sources"]["sort"] += 1
                    return
                node = node.func.value
            elif isinstance(node, ast.Attribute):
                node = node.value
            else:
                return

    def _index_keys(self, node: Optional[ast.AST]) -> Any:
        if node is None:
            return None
        s = _const_str(node)
        if s is not None:
            return [[s, 1]]
        if isinstance(node, (ast.List, ast.Tuple)):
            out = []
            for e in node.elts:
                if isinstance(e, ast.Tuple) and len(e.elts) == 2:
                    out.append([_const_str(e.elts[0]) or _unparse(e.elts[0]), _unparse(e.elts[1])])
                elif _const_str(e) is not None:
                    out.append([_const_str(e), 1])
                else:
                    out.append([_unparse(e), "?"])
            # [("field", 1)] where the list itself is a single pair tuple
            return out
        return _unparse(node)

    def _record_index(self, cname: str, c: Dict[str, Any], call: ast.Call) -> None:
        method = call.func.attr  # type: ignore[union-attr]
        entries = []
        if method == "create_index":
            entries.append({
                "keys": self._index_keys(call.args[0] if call.args else None),
                "options": {k.arg: _unparse(k.value) for k in call.keywords if k.arg},
            })
        else:
            lst = call.args[0] if call.args else None
            for e in getattr(lst, "elts", []) or []:
                if isinstance(e, ast.Call):
                    entries.append({
                        "keys": self._index_keys(e.args[0] if e.args else None),
                        "options": {k.arg: _unparse(k.value) for k in e.keywords if k.arg},
                    })
            if not entries:
                entries.append({"keys": _unparse(lst), "options": {}})
        for e in entries:
            rec = {"collection": cname, "file": self.rel, "line": call.lineno, "call": method, **e}
            self.inv.indexes.append(rec)
            c["indexes"].append({k: rec[k] for k in ("file", "line", "keys", "options")})

    def collect_declared_index_specs(self) -> None:
        """Data-driven index tables, e.g. ``INDEXES = {"users": [{"keys": [...], "unique": True}]}``."""
        for stmt in self.tree.body:
            if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
                continue
            if "INDEX" not in stmt.targets[0].id.upper() or not isinstance(stmt.value, ast.Dict):
                continue
            for k, v in zip(stmt.value.keys, stmt.value.values):
                cname = _const_str(k)
                if cname is None or not isinstance(v, (ast.List, ast.Tuple)):
                    continue
                for spec in v.elts:
                    if not isinstance(spec, ast.Dict):
                        continue
                    d = {(_const_str(a) or _unparse(a)): b for a, b in zip(spec.keys, spec.values) if a is not None}
                    if "keys" not in d:
                        continue
                    rec = {"collection": cname, "file": self.rel, "line": spec.lineno,
                           "call": "declared:" + stmt.targets[0].id,
                           "keys": self._index_keys(d["keys"]),
                           "options": {a: _unparse(b) for a, b in d.items() if a != "keys"}}
                    self.inv.indexes.append(rec)
                    c = self._ref(cname, spec.lineno, "index_spec")
                    c["indexes"].append({x: rec[x] for x in ("file", "line", "keys", "options", "call")})

    # -------------------------------------------------------------- pydantic
    def collect_models(self) -> None:
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [_unparse(b) for b in node.bases]
            fields = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields[stmt.target.id] = {"type": _unparse(stmt.annotation), "default": _unparse(stmt.value) if stmt.value is not None else None}
                elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    # Enum members: PENDING = "pending"
                    v = stmt.value
                    if isinstance(v, ast.Constant):
                        fields[stmt.targets[0].id] = {"type": "enum_member", "default": repr(v.value)}
            key = node.name
            if key in self.inv.models:
                key = f"{node.name}@{self.rel}"
            self.inv.models[key] = {"name": node.name, "file": self.rel, "line": node.lineno, "bases": bases, "fields": fields}


def _filter_models(models: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Keep only classes that (transitively) derive from BaseModel or Enum."""
    by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in models.values():
        by_name[m["name"]].append(m)
    keep_cache: Dict[str, bool] = {}

    def is_kept(name: str, seen: Set[str]) -> bool:
        if name in keep_cache:
            return keep_cache[name]
        if name in seen:
            return False
        seen.add(name)
        result = False
        for m in by_name.get(name, []):
            for b in m["bases"]:
                bn = b.split(".")[-1].split("[")[0]
                if bn in {"BaseModel", "Enum", "str, Enum", "IntEnum", "StrEnum"} or is_kept(bn, seen):
                    result = True
        keep_cache[name] = result
        return result

    return {k: v for k, v in models.items() if is_kept(v["name"], set())}


def analyse_source(source: str, rel: str = "<snippet>", inv: Optional[Inventory] = None) -> Inventory:
    inv = inv or Inventory()
    tree = ast.parse(source, filename=rel)
    fa = FileAnalyser(inv, rel, tree)
    fa.run()
    fa.collect_declared_index_specs()
    fa.collect_models()
    inv.files_scanned += 1
    return inv


def analyse_tree(root: str, base: Optional[str] = None) -> Dict[str, Any]:
    inv = Inventory()
    base = base or os.path.dirname(os.path.abspath(root))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in {"__pycache__", "node_modules", ".venv", "venv"})
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, base)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                analyse_source(src, rel, inv)
            except SyntaxError as exc:
                inv.parse_errors.append({"file": rel, "error": f"SyntaxError line {exc.lineno}: {exc.msg}"})
            except Exception as exc:  # pragma: no cover - defensive
                inv.parse_errors.append({"file": rel, "error": f"{type(exc).__name__}: {exc}"})
    out = inv.to_json(os.path.relpath(root, base))
    out["pydantic_models"] = _filter_models(out["pydantic_models"])
    return out


def main(argv: Optional[List[str]] = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.join(repo, "backend"), help="directory to scan (default: backend/)")
    ap.add_argument("-o", "--output", help="write JSON here instead of stdout")
    ap.add_argument("positional_output", nargs="?", help="alternative way to give the output path")
    ns = ap.parse_args(argv)
    result = analyse_tree(ns.root, base=repo)
    text = json.dumps(result, indent=2, sort_keys=False, default=str)
    out = ns.output or ns.positional_output
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {out}: {result['collection_count']} collections, {len(result['indexes'])} index specs, "
              f"{len(result['parse_errors'])} parse errors", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

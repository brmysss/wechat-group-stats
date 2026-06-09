#!/usr/bin/env python3
"""Run SQL on Supabase via Management API — token read from temp file."""
import json, urllib.request as ur, sys

with open("/tmp/supabase_token.txt", "r") as f:
    TOKEN = f.read().strip()

REF = "zycgwpaqmjwmliyhcwiv"
SQL_FILE = sys.argv[1] if len(sys.argv) > 1 else "/Users/allen/wechat-group-stats/docs/schema.sql"

with open(SQL_FILE, "r") as f:
    sql = f.read()

lines = sql.split("\n")
stmts = []
current = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith("--") or not stripped:
        continue
    current.append(line)
    if stripped.endswith(";"):
        stmts.append("\n".join(current))
        current = []

ok = 0
err = 0
for i, stmt in enumerate(stmts):
    data = json.dumps({"query": stmt}).encode()
    req = ur.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=data,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with ur.urlopen(req, timeout=30) as resp:
            urllib.request.urlopen(req)
            ok += 1
    except Exception as e:
        err += 1
        body = ""
        if hasattr(e, 'read'):
            body = e.read().decode()[:300]
        print(f"[{i+1}/{len(stmts)}] FAIL: {body}")
        if err > 2:
            break

print(f"Done: {ok} OK, {err} errors")

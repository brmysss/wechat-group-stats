#!/usr/bin/env python3
"""Write .env using binary I/O — secrets never appear in source."""
import os

target = os.path.expanduser("~/wechat-group-stats/web/.env")

# Read secrets from temp file
with open("/tmp/hermes_env_secrets.txt", "rb") as f:
    lines = f.read().strip().split(b"\n")
AUTH = lines[0]
SYNC = lines[1]
ADMIN = lines[2]

# Template with byte-level placeholders
tmpl = (
    b"# === 数据库 ===\n"
    b"# 先去 Supabase 创建项目，然后填下面的连接字符串\n"
    b"DATABASE_URL=[[[DATABASE_URL]]]\n"
    b"\n"
    b"# === 认证密钥（已自动生成） ===\n"
    b"AUTH_SECRET=[[[AUTH]]]\n"
    b"\n"
    b"# === 同步 API Key（已自动生成） ===\n"
    b"SYNC_API_KEY=[[[SYNC]]]\n"
    b"\n"
    b"# === 管理员密钥 ===\n"
    b"ADMIN_SECRET=[[[ADMIN]]]\n"
)

# Binary replace — no string interpolation
tmpl = tmpl.replace(b"[[[AUTH]]]", AUTH)
tmpl = tmpl.replace(b"[[[SYNC]]]", SYNC)
tmpl = tmpl.replace(b"[[[ADMIN]]]", ADMIN)

with open(target, "wb") as f:
    f.write(tmpl)

# Verify
exec(open(target, "rb").read())
print(".env written successfully")

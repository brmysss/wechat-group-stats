#!/usr/bin/env python3
"""
sync_avatars.py — 从本地微信 contact DB 同步头像 URL 到 Supabase
匹配链路: user.wxid → contact.username(加密) → small_head_url
"""
import sys, sqlite3
from pathlib import Path

sys.path.insert(0, '/Users/allen/wechat-group-stats')
from score_messages_v3 import read_db_url
import psycopg2

CONTACT_DB = Path.home() / "wechat-decrypt" / "decrypted" / "contact" / "contact.db"

# 1. 从 contact DB 构建 wxid → avatar_url 映射
print(f"[1] 读取联系人头像...")
conn_contact = sqlite3.connect(str(CONTACT_DB))
avatar_map = {}
for row in conn_contact.execute("SELECT username, encrypt_username, small_head_url, nick_name FROM contact WHERE small_head_url IS NOT NULL AND small_head_url != ''"):
    username, enc, url, nick = row
    if url and '/mmhead/' in url:
        avatar_map[username] = url
        if enc:
            avatar_map[enc] = url
conn_contact.close()
print(f"    找到 {len(avatar_map)} 个头像")

# 2. 从 Supabase 获取所有用户
print(f"[2] 查询 Supabase 用户...")
conn_db = psycopg2.connect(read_db_url())
cur = conn_db.cursor()
cur.execute('SELECT id, username, wxid FROM users')
users = cur.fetchall()
print(f"    {len(users)} 个用户")

# 3. 匹配并更新
print(f"[3] 匹配头像...")
updated = 0
misses = 0
for uid, name, wxid in users:
    if not wxid:
        misses += 1
        continue
    url = avatar_map.get(wxid)
    if url:
        cur.execute('UPDATE users SET "avatarUrl" = %s WHERE id = %s', (url, uid))
        updated += 1
        print(f"    ✅ {name:15s} → {url[:50]}...")
    else:
        misses += 1

conn_db.commit()
conn_db.close()
print(f"\n✅ 完成: {updated} 个匹配, {misses} 个无头像")

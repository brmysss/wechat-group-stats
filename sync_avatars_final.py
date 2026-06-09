#!/usr/bin/env python3
"""终极修复：unknown_xxx → 提取数字 = contact_id → 头像URL"""
import sys, sqlite3, re
from pathlib import Path
sys.path.insert(0, '/Users/allen/wechat-group-stats')
from score_messages_v3 import read_db_url
import psycopg2

# Build contact_id → avatar_url from contact DB
CONTACT_DB = Path.home() / "wechat-decrypt" / "decrypted" / "contact" / "contact.db"
conn_c = sqlite3.connect(str(CONTACT_DB))
id_to_avatar = {}
id_to_nick = {}
for row in conn_c.execute("SELECT id, small_head_url, nick_name FROM contact WHERE small_head_url LIKE '%mmhead%'"):
    id_to_avatar[row[0]] = row[1]
    id_to_nick[row[0]] = row[2]
conn_c.close()
print(f"Contact 头像: {len(id_to_avatar)} 个")

# Match unknown users
db = psycopg2.connect(read_db_url())
cur = db.cursor()
cur.execute('SELECT id, username, wxid FROM users WHERE wxid LIKE %s AND "avatarUrl" IS NULL', ('unknown_%',))
unknowns = cur.fetchall()
print(f"unknown_xxx 用户: {len(unknowns)}")

updated = 0
for uid, uname, wxid in unknowns:
    # 从 wxid 提取数字: unknown_104 → 104
    m = re.search(r'unknown_(\d+)', wxid)
    if m:
        cid = int(m.group(1))
        if cid in id_to_avatar:
            cur.execute('UPDATE users SET "avatarUrl" = %s WHERE id = %s', (id_to_avatar[cid], uid))
            updated += 1
            print(f"  ✅ {uname:15s} contact_id={cid} nick={id_to_nick.get(cid, '?')[:15]}")
        else:
            print(f"  ❌ {uname:15s} contact_id={cid} 无头像")

# Also fix punk2898 (fake wxid) by matching display name
# punk2898's wxid is 'punk2898_wxid' — this won't match anything
# But we can find it by going through the message DB for the sender

db.commit()

cur.execute('SELECT COUNT(*) FROM users WHERE "avatarUrl" IS NOT NULL')
has = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM users')
total = cur.fetchone()[0]
print(f"\n✅ 追加 {updated} → 最终 {has}/{total} 有头像")

# Show remaining missing
cur.execute('SELECT username, wxid FROM users WHERE "avatarUrl" IS NULL')
missing = cur.fetchall()
print(f"仍缺: {len(missing)}")
for r in missing[:15]:
    print(f"  {r[0]:15s} {r[1] or 'NULL'}")

db.close()

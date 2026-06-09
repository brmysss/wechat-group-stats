#!/usr/bin/env python3
"""
sync_avatars_v2.py — 正确的头像同步
映射链: user.wxid → 消息DB real_sender_id → contact.id → small_head_url
"""
import sys, sqlite3, hashlib, re
from pathlib import Path

sys.path.insert(0, '/Users/allen/wechat-group-stats')
from score_messages_v3 import read_db_url
import psycopg2

BASE = Path("/Users/allen/wechat-group-stats")
CONTACT_DB = Path.home() / "wechat-decrypt" / "decrypted" / "contact" / "contact.db"
MESSAGE_DIR = Path.home() / "wechat-decrypt" / "decrypted" / "message"
TARGET_GROUP = "45379818937@chatroom"

# ── Step 1: 从消息DB构建 sender_id → wxid 映射 ──
print("[1] 从消息DB解析 sender_id → wxid...")
md5 = hashlib.md5(TARGET_GROUP.encode()).hexdigest()
table_name = f"Msg_{md5}"

sender_to_wxid = {}
message_dbs = sorted([str(p) for p in MESSAGE_DIR.glob("message_*.db")
                       if p.name.startswith("message_") and not p.name.endswith("_fts.db")])

for db_path in message_dbs:
    conn = sqlite3.connect(db_path)
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    if not exists:
        conn.close()
        continue

    # 获取这个DB里所有的sender_id
    rows = conn.execute(
        f'SELECT DISTINCT real_sender_id FROM [{table_name}] WHERE real_sender_id IS NOT NULL'
    ).fetchall()

    for (sid,) in rows:
        if sid in sender_to_wxid:
            continue
        row = conn.execute(
            f"""SELECT message_content FROM [{table_name}]
                WHERE real_sender_id=? AND message_content IS NOT NULL AND message_content != ''
                AND (WCDB_CT_message_content IS NULL OR WCDB_CT_message_content = 0)
                LIMIT 1""",
            (sid,)
        ).fetchone()
        if row and row[0]:
            text = row[0] if isinstance(row[0], str) else row[0].decode('utf-8', errors='replace')
            m = re.match(r'(wxid_[a-zA-Z0-9]+):\n', text)
            if m:
                sender_to_wxid[sid] = m.group(1)
    conn.close()

print(f"   解析出 {len(sender_to_wxid)} 个 wxid")

# ── Step 2: 从contact DB构建 contact_id → avatar_url ──
print("[2] 读取contact头像...")
conn_c = sqlite3.connect(str(CONTACT_DB))
id_to_avatar = {}
for row in conn_c.execute("SELECT id, small_head_url, nick_name FROM contact WHERE small_head_url IS NOT NULL AND small_head_url != ''"):
    cid, url, nick = row
    if '/mmhead/' in url:
        id_to_avatar[cid] = url
conn_c.close()
print(f"   找到 {len(id_to_avatar)} 个头像")

# ── Step 3: 构建 wxid → avatar_url ──
print("[3] 构建 wxid → avatar 映射...")
# 反向: sender_id → wxid, contact_id = sender_id
wxid_to_avatar = {}
for sender_id, wxid in sender_to_wxid.items():
    if sender_id in id_to_avatar:
        wxid_to_avatar[wxid] = id_to_avatar[sender_id]

print(f"   匹配到头像的 wxid: {len(wxid_to_avatar)}")

# ── Step 4: 更新 Supabase ──
print("[4] 更新 Supabase...")
conn_db = psycopg2.connect(read_db_url())
cur = conn_db.cursor()
cur.execute('SELECT id, username, wxid FROM users')
users = cur.fetchall()

updated = 0
misses = 0
for uid, name, wxid in users:
    if not wxid or wxid.startswith('unknown_') or wxid == 'Allen Dily':
        misses += 1
        continue
    url = wxid_to_avatar.get(wxid)
    if url:
        cur.execute('UPDATE users SET "avatarUrl" = %s WHERE id = %s', (url, uid))
        updated += 1

conn_db.commit()
conn_db.close()

print(f"✅ 更新: {updated} 个, 跳过: {misses} 个")

# 统计
cur2 = psycopg2.connect(read_db_url()).cursor()
cur2.execute('SELECT COUNT(*) FROM users WHERE "avatarUrl" IS NOT NULL')
total_has = cur2.fetchone()[0]
cur2.execute('SELECT COUNT(*) FROM users')
total = cur2.fetchone()[0]
cur2.connection.close()
print(f"   头像覆盖率: {total_has}/{total}")

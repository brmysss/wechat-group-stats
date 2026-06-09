#!/usr/bin/env python3
"""评分后处理 v2：逐条改名 + 同步头像，遇错不中断"""
import sys, sqlite3, re, hashlib
from pathlib import Path

sys.path.insert(0, "/Users/allen/wechat-group-stats")
from score_messages_v3 import read_db_url
import psycopg2

BASE = Path("/Users/allen/wechat-group-stats")
CONTACT_DB = Path.home() / "wechat-decrypt" / "decrypted" / "contact" / "contact.db"
MESSAGE_DIR = Path.home() / "wechat-decrypt" / "decrypted" / "message"
TARGET_GROUP = "45379818937@chatroom"

# wxid映射
md5 = hashlib.md5(TARGET_GROUP.encode()).hexdigest()
table_name = f"Msg_{md5}"
sender_to_wxid = {}
for db_path in sorted([str(p) for p in MESSAGE_DIR.glob("message_*.db") if p.name.startswith("message_") and not p.name.endswith("_fts.db")]):
    conn = sqlite3.connect(db_path)
    if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone():
        conn.close(); continue
    for (sid,) in conn.execute(f"SELECT DISTINCT real_sender_id FROM [{table_name}] WHERE real_sender_id IS NOT NULL"):
        if sid in sender_to_wxid: continue
        row = conn.execute(f"SELECT message_content FROM [{table_name}] WHERE real_sender_id=? AND message_content IS NOT NULL AND message_content != '' AND (WCDB_CT_message_content IS NULL OR WCDB_CT_message_content = 0) LIMIT 1", (sid,)).fetchone()
        if row and row[0]:
            text = row[0] if isinstance(row[0], str) else row[0].decode('utf-8', errors='replace')
            m = re.match(r'(wxid_[a-zA-Z0-9]+):\n', text)
            if m: sender_to_wxid[sid] = m.group(1)
    conn.close()

# contact头像 + 昵称
conn_c = sqlite3.connect(str(CONTACT_DB))
contact = {}
for row in conn_c.execute("SELECT id, nick_name, remark, small_head_url FROM contact"):
    cid, nick, remark, url = row
    if url and '/mmhead/' in url:
        contact[cid] = (nick or "", remark or "", url)
conn_c.close()

wxid_to_avatar = {wxid: contact[sid][2] for sid, wxid in sender_to_wxid.items() if sid in contact}

print(f"wxid: {len(sender_to_wxid)} | contact: {len(contact)} | 头像映射: {len(wxid_to_avatar)}")

# 处理 Supabase
db = psycopg2.connect(read_db_url())
cur = db.cursor()
cur.execute("SELECT id, username, wxid FROM users")
users = cur.fetchall()

renamed = avatar_set = errors = 0

for uid, uname, wxid in users:
    # 改名
    if wxid and wxid.startswith('unknown_'):
        m = re.search(r'unknown_(\d+)', wxid)
        if m:
            cid = int(m.group(1))
            info = contact.get(cid)
            if info:
                real_name = info[1] or info[0]
                if real_name and real_name != uname:
                    try:
                        cur.execute('UPDATE users SET username = %s WHERE id = %s', (real_name, uid))
                        db.commit()
                        renamed += 1
                    except Exception as e:
                        db.rollback()
                        errors += 1

    # 头像
    if wxid:
        url = wxid_to_avatar.get(wxid)
        if url:
            try:
                cur.execute('UPDATE users SET "avatarUrl" = %s WHERE id = %s AND "avatarUrl" IS NULL', (url, uid))
                db.commit()
                avatar_set += 1
            except:
                db.rollback()

cur.execute("SELECT COUNT(*) FROM users"); total = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM users WHERE "avatarUrl" IS NOT NULL'); has = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM users WHERE wxid LIKE 'unknown_%'"); unk = cur.fetchone()[0]

print(f"\n✅ 改名 {renamed} | 头像 {avatar_set} | 错误 {errors}")
print(f"用户: {total} | 有头像: {has} | 仍 unknown: {unk}")

# Allen Dily 改成 punk老板
try:
    cur.execute("UPDATE users SET username = 'punk老板' WHERE username = 'Allen Dily'")
    db.commit()
    print("✅ Allen Dily → punk老板")
except:
    db.rollback()
    print("⚠️ 改名 Allen Dily 失败（可能已有 punk老板）")

db.close()

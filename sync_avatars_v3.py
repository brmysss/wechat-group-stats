#!/usr/bin/env python3
"""解码 unknown_xxx 用户：通过 chatroom_member → contact → 头像"""
import sys, sqlite3
from pathlib import Path
from collections import defaultdict

CONTACT_DB = Path.home() / "wechat-decrypt" / "decrypted" / "contact" / "contact.db"
TARGET_GROUP = "45379818937@chatroom"

conn = sqlite3.connect(str(CONTACT_DB))

# 1. 找到目标群的 room_id
room_id = None
for row in conn.execute("SELECT id, username FROM chat_room WHERE username = ?", (TARGET_GROUP,)):
    room_id = row[0]
    print(f"Room ID: {room_id}")

if not room_id:
    print("找不到目标群!")
    conn.close()
    sys.exit(1)

# 2. 获取该群所有成员 member_id
member_ids = [r[0] for r in conn.execute(
    "SELECT member_id FROM chatroom_member WHERE room_id = ?", (room_id,)
).fetchall()]
print(f"群成员数: {len(member_ids)}")

# 3. 查询这些成员的 contact 信息 (id, username, nick_name, small_head_url)
placeholders = ','.join('?' * len(member_ids))
rows = conn.execute(
    f"SELECT id, username, nick_name, small_head_url, remark, alias FROM contact WHERE id IN ({placeholders})",
    member_ids
).fetchall()

# 构建多个匹配维度
by_id = {}           # contact.id → avatar
by_enc_wxid = {}     # encrypted username → avatar  
by_nick = {}         # nick_name → avatar
by_remark = {}       # remark → avatar

for (cid, username, nick, url, remark, alias) in rows:
    if not url or '/mmhead/' not in url:
        continue
    by_id[cid] = url
    if username:
        by_enc_wxid[username] = url
    if nick:
        # 如果有重名，保留第一个
        if nick not in by_nick:
            by_nick[nick] = url
    if remark:
        if remark not in by_remark:
            by_remark[remark] = url

print(f"有头像的成员: {len(by_id)}/{len(member_ids)}")

# 4. 统计昵称匹配可行性
# 看看 group_stats 里的 tag 和 contact 里的 nick_name 重叠情况
conn.close()

# 查 Supabase 中 unknown_xxx 用户的 tag
sys.path.insert(0, '/Users/allen/wechat-group-stats')
from score_messages_v3 import read_db_url
import psycopg2

db = psycopg2.connect(read_db_url())
cur = db.cursor()

# 获取所有 unknown_xxx 用户的 wxid
cur.execute("""SELECT u.id, u.username, u.wxid, gs.tag 
    FROM users u 
    LEFT JOIN group_stats gs ON u.wxid = gs."senderWxid"
    WHERE u.wxid LIKE 'unknown_%%' AND u."avatarUrl" IS NULL""")
unknowns = cur.fetchall()
print(f"\nunknown_xxx 用户: {len(unknowns)}")

# 尝试用 senderWxid 匹配
# senderWxid 格式是 unknown_104 之类，但我们需要的是真实的 member_id
# group_stats.senderWxid 是评分脚本写入的 wxid（已解析或 unknown_xxx）
# 实际上 group_stats 的 senderWxid 字段名有误导性——它就是 wxid 或 fallback

# 换个思路：group_stats 有 tag 字段——这是群昵称
# 对于 unknown 用户，tag 可能匹配 contact.nick_name

matched_by_tag = 0
for uid, uname, wxid, tag in unknowns:
    if tag and (tag in by_nick or tag in by_remark):
        url = by_nick.get(tag) or by_remark.get(tag)
        cur.execute('UPDATE users SET "avatarUrl" = %s WHERE id = %s', (url, uid))
        matched_by_tag += 1
        print(f"  ✅ {uname:15s} tag='{tag}' → {url[:50]}...")

db.commit()

# 再查还有多少没头像的
cur.execute('SELECT COUNT(*) FROM users WHERE "avatarUrl" IS NULL')
missing = cur.fetchone()[0]
total = cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]
print(f"\n通过昵称匹配: +{matched_by_tag}")
print(f"最终: {total - missing}/{total} 有头像 ({missing} 缺失)")

db.close()

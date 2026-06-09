#!/usr/bin/env python3
import sys, os
os.chdir('/Users/allen/wechat-group-stats')
sys.path.insert(0, str(os.getcwd()))
import psycopg2
from score_messages_v3 import read_db_url

db = psycopg2.connect(read_db_url())
cur = db.cursor()

cur.execute("SELECT COUNT(*) FROM users"); total = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM users WHERE "avatarUrl" IS NOT NULL'); has = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM users WHERE wxid IS NULL"); nw = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM users WHERE wxid LIKE 'unknown_%'"); unk = cur.fetchone()[0]

print(f"总用户: {total} | 有头像: {has} | wxid=NULL: {nw} | unknown: {unk}")

cur.execute("""
    SELECT username, wxid, "inviteCode", "createdAt" 
    FROM users WHERE wxid IS NULL 
    ORDER BY "createdAt" DESC LIMIT 5
""")
print("\nwxid=NULL 的用户:")
for r in cur.fetchall():
    print(f"  {r[0]:25s} code={r[2][:15]} created={r[3]}")

# 检查 Allen Dily / punk老板
cur.execute("SELECT username, wxid, \"avatarUrl\" FROM users WHERE username IN ('Allen Dily', 'punk老板')")
print("\n关键用户:")
for r in cur.fetchall():
    print(f"  {r[0]:15s} wxid={r[1]} av={'Y' if r[2] else 'N'}")

db.close()

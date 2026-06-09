#!/usr/bin/env python3
"""清空 users + scores 表（保留 invite_codes, rewards, redemptions）"""
import sys; sys.path.insert(0, "/Users/allen/wechat-group-stats")
from score_messages_v3 import read_db_url
import psycopg2

db = psycopg2.connect(read_db_url())
cur = db.cursor()

# Show before counts
cur.execute("SELECT COUNT(*) FROM users"); u_before = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM scores"); s_before = cur.fetchone()[0]
print(f"清空前: {u_before} users, {s_before} scores")

# Clear (order matters for FK)
cur.execute("DELETE FROM scores")
cur.execute("DELETE FROM users")
db.commit()

cur.execute("SELECT COUNT(*) FROM users"); print(f"清空后: {cur.fetchone()[0]} users")
cur.execute("SELECT COUNT(*) FROM scores"); print(f"清空后: {cur.fetchone()[0]} scores")
print("✅ 完成")
db.close()

#!/usr/bin/env python3
"""
score_messages.py — DeepSeek AI 消息评分引擎 v2
================================================
v2 优化:
  - 活跃度：纯数据驱动（消息数 + 活跃天数），不浪费 API
  - 批量：一次 API 调用评 10 个人（batch_size=10）
  - 并发：ThreadPoolExecutor 5 workers 并行请求
  - 速度：141 人 → ~15 批 → 3 轮并发 → ~30 秒

用法:
  python score_messages.py                          # 默认：近双周消息
  python score_messages.py --days 14                # 指定天数
  python score_messages.py --dry-run                # 只分析不写入 Supabase
  python score_messages.py --concurrency 8          # 自定义并发数
  python score_messages.py --batch-size 15          # 自定义批量大小
"""

import sys
import os
import json
import hashlib
import sqlite3
import argparse
import uuid
import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

# ── 路径 ──
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("wechat_stats", str(BASE_DIR / "wechat-stats.py"))
wechat_stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wechat_stats)
extract_messages_for_push = wechat_stats.extract_messages_for_push
resolve_sender_wxid = wechat_stats.resolve_sender_wxid
build_contact_map = wechat_stats.build_contact_map

# ── 常量 ──
TARGET_GROUP = "45379818937@chatroom"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_DAYS = 14
DEFAULT_SAMPLE = 15          # 每人最多采样 N 条给 AI 分析
DEFAULT_BATCH_SIZE = 10      # 每批评多少人
DEFAULT_CONCURRENCY = 5      # 并发数


# ═══════════════════════════════════════════════
#  活跃度：纯数据驱动（不浪费 API）
# ═══════════════════════════════════════════════

def calc_active_score(msg_count: int, distinct_days: int) -> float:
    """
    基于两个指标计算活跃度 0-10：
      - msg_count：周期内发言总数
      - distinct_days：有发言的天数

    逻辑：用百分位映射，避免绝对阈值
    msg_count 权重 60%，distinct_days 权重 40%
    """
    # msg_count → 0-10 (对数压缩 + 百分位)
    # distinct_days → 0-10 (线性，max=周期天数)
    return round(msg_count * 0.6 + distinct_days * 0.4, 1)


def calc_active_scores(by_sender: dict, total_days: int) -> dict:
    """
    输入：{sender_id: [msg, msg, ...]}
    输出：{sender_id: active_score_0_to_10}
    """
    # 收集原始数据
    raw = {}
    for sid, msgs in by_sender.items():
        days = set()
        for m in msgs:
            days.add(datetime.fromtimestamp(m["sent_at"]).date())
        raw[sid] = {
            "msg_count": len(msgs),
            "distinct_days": len(days),
        }

    # 归一化到 0-10
    # msg_count: 取对数后归一化
    counts = [r["msg_count"] for r in raw.values()]
    days_list = [r["distinct_days"] for r in raw.values()]

    import math
    max_count = max(counts) if counts else 1
    max_days = max(days_list) if days_list else total_days

    scores = {}
    for sid, r in raw.items():
        # 对数归一化（避免极值拉偏）
        if max_count > 1:
            msg_norm = math.log(r["msg_count"] + 1) / math.log(max_count + 1)
        else:
            msg_norm = 0
        day_norm = r["distinct_days"] / max(max_days, 1)

        scores[sid] = round(msg_norm * 6 + day_norm * 4, 1)

    return scores


# ═══════════════════════════════════════════════
#  批量评分 Prompt（一次评多人）
# ═══════════════════════════════════════════════

BATCH_SCORING_PROMPT = """你是一个高质量社群的评估员。对下列 N 位群成员进行内容质量评分。

## 每个人物给出三个维度 (0-10)：

- **sharer (分享价值)**：分享有价值的信息、链接、见解、工具
- **researcher (研究深度)**：深入分析、原创思考、数据支撑、系统性输出
- **collaborator (协作精神)**：帮助他人、回答问题、协调分歧、维护氛围

## 龙珠提名规则：
- ❌ 无实质内容发言（仅表情、闲聊、一句话）→ 不提名
- ✅ 持续输出高质量内容 + 帮助他人 → 提名
- ✅ 深度研究/教程/系统性分享 → 提名
- 每人最多 1 颗，本批最多 3 颗

## 输出格式（严格 JSON array，无 markdown 包裹）：
[
  {"id": "name1", "sharer": 0-10, "researcher": 0-10, "collaborator": 0-10, "summary": "一句话总结", "dragon_nominee": true/false},
  {"id": "name2", ...}
]

## 消息（格式：日期 内容）：
"""


# ═══════════════════════════════════════════════
#  数据抽取
# ═══════════════════════════════════════════════

def get_message_dbs():
    decrypt_dir = Path.home() / "wechat-decrypt" / "decrypted" / "message"
    return sorted([
        str(p) for p in decrypt_dir.glob("message_*.db")
        if p.name.startswith("message_") and not p.name.endswith("_fts.db")
    ])

def get_contact_db():
    return Path.home() / "wechat-decrypt" / "decrypted" / "contact" / "contact.db"


def extract_and_group(days: int):
    """抽取消息 → 按发送者分组 → 解析显示名 → 计算活跃度"""
    since_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    message_dbs = get_message_dbs()
    contact_db = get_contact_db()

    print(f"[*] 抽取 {days} 天内消息 ({datetime.fromtimestamp(since_ts).strftime('%m/%d')} ~ {datetime.now().strftime('%m/%d')})")
    print(f"[*] 消息 DB: {len(message_dbs)} 个文件")

    messages = extract_messages_for_push(contact_db, message_dbs, TARGET_GROUP, since_ts)
    print(f"[+] {len(messages)} 条消息")

    by_sender = defaultdict(list)
    for msg in messages:
        by_sender[msg["sender_id"]].append(msg)

    # 解析显示名
    sender_ids = list(by_sender.keys())
    _, contact_by_wxid = build_contact_map(contact_db)
    wxid_map = resolve_sender_wxid(contact_db, message_dbs, TARGET_GROUP, sender_ids)
    display_names = {}
    resolved_wxid = {}  # sender_id → 微信原始 wxid 字符串
    for sid in sender_ids:
        v = wxid_map.get(sid)
        w = v[0] if isinstance(v, tuple) else v
        resolved_wxid[sid] = w if w else f"unknown_{sid}"
        display_names[sid] = contact_by_wxid.get(w, str(w)) if w else f"u{sid}"

    # 活跃度（数据驱动）
    active_scores = calc_active_scores(by_sender, days)

    return by_sender, display_names, active_scores, resolved_wxid


# ═══════════════════════════════════════════════
#  DeepSeek API 调用
# ═══════════════════════════════════════════════

def call_deepseek_batch(api_key: str, batch: list[tuple]) -> dict:
    """
    批量调用：一次 API 评多人
    batch: [(sender_id, name, messages_text), ...]
    返回: {sender_id: score_dict, ...}
    """
    if not batch:
        return {}

    # 构建 prompt
    parts = []
    for sid, name, msg_text in batch:
        parts.append(f"\n## {name}\n{msg_text}\n")

    prompt = BATCH_SCORING_PROMPT + "\n".join(parts)

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "只输出 JSON array，不要 markdown 代码块，不要额外文字。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
    )

    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    content = result["choices"][0]["message"]["content"]

    # 解析 JSON array
    scores_list = json.loads(content)
    # 兼容两种格式：直接的 array 或 {"members": [...]}
    if isinstance(scores_list, dict):
        scores_list = scores_list.get("members", scores_list.get("scores", []))

    # 映射回 sender_id
    result_map = {}
    for item in scores_list:
        item_id = item.get("id", "")
        # 匹配 batch 中的 name
        for sid, name, _ in batch:
            if item_id == name:
                result_map[sid] = {
                    "sharer": item.get("sharer", 0),
                    "researcher": item.get("researcher", 0),
                    "collaborator": item.get("collaborator", 0),
                    "summary": item.get("summary", ""),
                    "dragon_ball_nominee": item.get("dragon_nominee", item.get("dragon_ball_nominee", False)),
                }
                break

    return result_map


def prepare_batches(sampled_msgs: dict, display_names: dict, batch_size: int) -> list:
    """
    将用户分组打包成 batch
    每批格式: [(sender_id, name, messages_text), ...]
    """
    users = list(sampled_msgs.items())
    batches = []

    for i in range(0, len(users), batch_size):
        chunk = users[i:i + batch_size]
        batch = []
        for sender_id, msgs in chunk:
            name = display_names.get(sender_id, f"u{sender_id}")
            # 格式化消息
            msg_lines = []
            for m in msgs:
                ts = datetime.fromtimestamp(m["sent_at"]).strftime("%m-%d %H:%M")
                msg_lines.append(f"[{ts}] {m['content'][:200]}")
            msg_text = "\n".join(msg_lines)
            batch.append((sender_id, name, msg_text))
        batches.append(batch)

    return batches


# ═══════════════════════════════════════════════
#  并发评分引擎
# ═══════════════════════════════════════════════

def score_concurrent(api_key: str, batches: list, concurrency: int) -> dict:
    """并发评分所有 batch，收集结果"""
    all_scores = {}
    total = len(batches)
    completed = 0
    lock = __import__('threading').Lock()

    def score_one(batch_idx: int, batch: list) -> tuple:
        nonlocal completed
        batch_names = [name for _, name, _ in batch]
        try:
            result = call_deepseek_batch(api_key, batch)
            noms = []
            for sid_, name_, _ in batch:
                if result.get(sid_, {}).get("dragon_ball_nominee"):
                    noms.append(name_)
            with lock:
                completed += 1
                print(f"  [{completed}/{total}] ✅ 批{batch_idx+1} {len(result)}人 {', '.join(batch_names[:3])}..." +
                      (f" 🐉 {noms[0]}" if noms else ""))
            return (batch_idx, result, None)
        except Exception as e:
            with lock:
                completed += 1
                print(f"  [{completed}/{total}] ❌ 批{batch_idx+1}: {str(e)[:60]}")
            # 失败返回零分
            fail_scores = {}
            for sid, name, _ in batch:
                fail_scores[sid] = {"sharer": 0, "researcher": 0, "collaborator": 0, "summary": "", "dragon_ball_nominee": False}
            return (batch_idx, fail_scores, str(e))

    print(f"\n=== DeepSeek 批量并发评分 ({total} 批 × 每批 ~{len(batches[0]) if batches else 0}人, {concurrency} 并发) ===\n")
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(score_one, i, batch): i for i, batch in enumerate(batches)}
        for future in as_completed(futures):
            _, result, err = future.result()
            all_scores.update(result)

    elapsed = time.time() - t0
    print(f"\n[⏱] 耗时 {elapsed:.1f}s — {len(all_scores)}/{sum(len(b) for b in batches)} 人评分完成")

    return all_scores


# ═══════════════════════════════════════════════
#  Supabase 推送
# ═══════════════════════════════════════════════

def read_db_url():
    env_path = BASE_DIR / "web" / ".env"
    if env_path.exists():
        with open(env_path, 'rb') as f:
            for line in f.read().decode().split('\n'):
                if line.startswith('DATABASE_URL='):
                    url = line.split('=', 1)[1].strip()
                    if '?pgbouncer=true' in url:
                        url = url.replace('?pgbouncer=true', '')
                    # psycopg2 不支持 no-verify，换成 require
                    url = url.replace('sslmode=no-verify', 'sslmode=require')
                    return url
    return None


def push_to_supabase(scores: dict, active_scores: dict, display_names: dict, wxid_map: dict, api_key: str):
    """推送评分到 Supabase scores 表。优先按 wxid 查找用户，避免同名碰撞。"""
    import psycopg2

    db_url = read_db_url()
    if not db_url:
        print("[!] 找不到 DATABASE_URL")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # 获取当前活跃周期
    cur.execute("SELECT id FROM cycles WHERE status='active' LIMIT 1")
    cycle_row = cur.fetchone()
    if not cycle_row:
        print("[!] 无活跃周期，跳过")
        conn.close()
        return
    cycle_id = cycle_row[0]

    now = datetime.now()
    inserted = 0
    new_users = 0
    backfilled = 0

    for sender_id, ai_score in scores.items():
        name = display_names.get(sender_id, f"u{sender_id}")
        wxid = wxid_map.get(sender_id, f"unknown_{sender_id}")
        active = active_scores.get(sender_id, 0)

        # 查找用户：优先按 wxid，其次按 username
        uid = None
        if wxid:
            cur.execute('SELECT id, username FROM users WHERE wxid = %s', (wxid,))
            row = cur.fetchone()
            if row:
                uid = row[0]
                # 如果显示名变了，更新 username
                if row[1] != name:
                    cur.execute('UPDATE users SET username = %s, "updatedAt" = %s WHERE id = %s', (name, now, uid))

        if not uid:
            # 按 username 查找（兼容旧数据）
            cur.execute('SELECT id, wxid FROM users WHERE username = %s', (name,))
            row = cur.fetchone()
            if row:
                uid = row[0]
                # 补填 wxid
                if not row[1]:
                    cur.execute('UPDATE users SET wxid = %s, "updatedAt" = %s WHERE id = %s', (wxid, now, uid))
                    backfilled += 1

        if not uid:
            # 创建新用户，带 wxid
            uid = str(uuid.uuid4())
            code = f"auto-{uuid.uuid4().hex[:8]}"
            cur.execute(
                'INSERT INTO users (id, username, wxid, "inviteCode", "createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, %s)',
                (uid, name, wxid, code, now, now)
            )
            new_users += 1

        dragon = 1 if ai_score.get("dragon_ball_nominee") else 0

        cur.execute('''
            INSERT INTO scores (id, "userId", "cycleId", "activePoints", "sharerPoints", "researcherPoints", "collaboratorPoints", "dragonBalls")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("userId", "cycleId") DO UPDATE SET
                "activePoints" = EXCLUDED."activePoints",
                "sharerPoints" = EXCLUDED."sharerPoints",
                "researcherPoints" = EXCLUDED."researcherPoints",
                "collaboratorPoints" = EXCLUDED."collaboratorPoints",
                "dragonBalls" = EXCLUDED."dragonBalls"
        ''', (
            str(uuid.uuid4()), uid, cycle_id,
            active,
            ai_score.get("sharer", 0),
            ai_score.get("researcher", 0),
            ai_score.get("collaborator", 0),
            dragon,
        ))
        inserted += 1

    conn.commit()

    cur.execute('SELECT COUNT(*), SUM("dragonBalls") FROM scores WHERE "cycleId" = %s', (cycle_id,))
    cnt, db = cur.fetchone()
    conn.close()

    print(f"\n✅ Supabase: {cnt} 条评分, {db or 0} 🐉 入库 | 新用户 {new_users} | 补填 wxid {backfilled}")


# ═══════════════════════════════════════════════
#  本地输出
# ═══════════════════════════════════════════════

def save_and_display(scores, active_scores, display_names, days):
    """保存本地 JSON + 打印排行榜"""
    # 合并总分
    combined = {}
    for sid, ai in scores.items():
        name = display_names.get(sid, f"u{sid}")
        active = active_scores.get(sid, 0)
        total = round(active + ai.get("sharer", 0) + ai.get("researcher", 0) + ai.get("collaborator", 0), 1)
        combined[name] = {
            "active": active,
            "sharer": ai.get("sharer", 0),
            "researcher": ai.get("researcher", 0),
            "collaborator": ai.get("collaborator", 0),
            "total": total,
            "summary": ai.get("summary", ""),
            "dragon_nominee": ai.get("dragon_ball_nominee", False),
        }

    # 排序
    ranked = sorted(combined.items(), key=lambda x: -x[1]["total"])

    # 保存
    output = {
        "analyzed_at": datetime.now().isoformat(),
        "days": days,
        "users": len(ranked),
        "scores": combined,
    }
    output_path = BASE_DIR / f"scores_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 同时更新 scores_latest.json
    with open(BASE_DIR / "scores_latest.json", 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 打印 top 10
    print(f"\n{'='*60}")
    print(f"  🏆 积分排行榜 Top 10 ({days}天周期)")
    print(f"{'='*60}")
    for i, (name, s) in enumerate(ranked[:10]):
        dragon = "🐉" if s["dragon_nominee"] else "  "
        bar = "█" * int(s["total"] / 3) if s["total"] > 0 else ""
        print(f"  {dragon} {i+1:2d}. {name[:16]:16s} 💬{s['active']:4.1f} 📤{s['sharer']:4.1f} 🔬{s['researcher']:4.1f} 🤝{s['collaborator']:4.1f}  = {s['total']:5.1f} {bar}")

    dragon_count = sum(1 for _, s in ranked if s["dragon_nominee"])
    print(f"\n  🐉 龙珠提名: {dragon_count} 人")
    print(f"\n  [+] 完整数据: {output_path}")

    return ranked


# ═══════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="DeepSeek AI 评分引擎 v2（批量+并发+数据驱动）")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # 读取 API key
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        key_file = Path("/tmp/deepseek_key.bin")
        if key_file.exists():
            with open(key_file, 'rb') as f:
                api_key = f.read().decode().strip()
    if not api_key:
        print("[!] 请设置 DEEPSEEK_API_KEY 或确保 /tmp/deepseek_key.bin 存在")
        sys.exit(1)

    print(f"╔══════════════════════════════════════════╗")
    print(f"║  DeepSeek AI 评分引擎 v2                 ║")
    print(f"║  批量 {args.batch_size}人/批 · {args.concurrency}并发 · 活跃度数据驱动 ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"  目标群: {TARGET_GROUP}")
    print(f"  周期: {args.days} 天 | 采样: {args.sample_size} 条/人\n")

    # 1. 抽取
    by_sender, display_names, active_scores, wxid_map = extract_and_group(args.days)
    if not by_sender:
        print("[!] 无消息")
        return
    print(f"  {len(by_sender)} 个发言人\n")

    # 2. 采样 + 打包
    sampled = {}
    for sid, msgs in by_sender.items():
        msgs_sorted = sorted(msgs, key=lambda m: -len(m["content"]))
        sampled[sid] = msgs_sorted[:args.sample_size]

    batches = prepare_batches(sampled, display_names, args.batch_size)
    print(f"[*] {len(sampled)} 人 → {len(batches)} 批 (每批 {args.batch_size} 人)")

    # 3. 并发评分
    ai_scores = score_concurrent(api_key, batches, args.concurrency)

    # 4. 输出
    ranked = save_and_display(ai_scores, active_scores, display_names, args.days)

    # 5. 推送 Supabase
    if not args.dry_run:
        print("\n=== 推送 Supabase ===")
        try:
            push_to_supabase(ai_scores, active_scores, display_names, wxid_map, api_key)
        except Exception as e:
            print(f"[!] Supabase 推送失败: {e}")

    print(f"\n✅ 完成")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
score_messages_v3.py — AI 评分引擎 v3：按天全量 + 上下文感知
==============================================================
v3 改进:
  - 清洗: < 8 字的纯水消息过滤（含纯 emoji/数字/标点）
  - 分组: 按自然日，每天整个会话喂给 AI
  - 上下文: AI 看到完整对话流，能判断谁问谁答谁分享
  - 输出: 逐条贡献标注存本地，最终汇总入 Supabase
  - 龙珠: 双周 Top 3 (sharer + researcher 总分最高者)
  - 活跃度: 纯数据驱动，不动

用法:
  python score_messages_v3.py                      # 默认: 近14天
  python score_messages_v3.py --days 7             # 7天
  python score_messages_v3.py --dry-run            # 只分析不写入 Supabase
  python score_messages_v3.py --days 14 --concurrency 6
"""

import sys
import os
import json
import re
import argparse
import uuid
import time
import math
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
DEFAULT_CONCURRENCY = 5
MIN_CONTENT_LENGTH = 8          # 低于8字过滤
MAX_MSG_PER_DAY = 600           # 单天超此阈值则按6h窗口再切
DRAGON_BALL_COUNT = 3           # 双周龙珠数量

# ── 清洗规则 ──

PURE_EMOJI_RE = re.compile(
    r'^[\U0001F300-\U0001F9FF\u2600-\u27BF\uFE00-\uFE0F'
    r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
    r'\u200D\u2194-\u2199\u21A9-\u21AA\u231A-\u231B'
    r'\u23CF\u23E9-\u23F3\u23F8-\u23FA\u24C2'
    r'\u25AA-\u25AB\u25B6\u25C0\u25FB-\u25FE'
    r'\u2600-\u27BF\u2934-\u2935\u2B05-\u2B07'
    r'\u2B1B-\u2B1C\u2B50\u2B55\u3030\u303D'
    r'\u3297\u3299\U0001F000-\U0001FFFF'
    r'\u200D\u20E3\uFE0F\u0023\u002A\u0030-\u0039'
    r'\s]*$',
    re.UNICODE
)

# 微信表情: [旺柴] [笑脸] [666] 等
BRACKET_EXPR_RE = re.compile(r'^\[[^]]{1,10}\]$')

SYSTEM_MSG_PATTERNS = [
    r'加入了群聊', r'退出了群聊', r'修改群名为',
    r'邀请.*加入了群聊', r'移出了群聊',
    r'撤回了一条消息', r'开启了朋友验证',
    r'你.*添加.*为朋友', r'以上是打招呼的内容',
    r'视频号', r'小程序', r'红包',
    r'转账', r'语音通话', r'视频通话',
    r'\[链接\]', r'文件传输助手',
]

def is_noise(content: str) -> bool:
    """判断消息是否为噪音（无需AI分析的）"""
    text = content.strip()

    # 空内容
    if not text:
        return True

    # 系统消息
    for pat in SYSTEM_MSG_PATTERNS:
        if re.search(pat, text):
            return True

    # 纯 emoji/表情
    if PURE_EMOJI_RE.match(text):
        return True

    # 微信表情: [旺柴] [笑脸] 等
    if BRACKET_EXPR_RE.match(text):
        return True

    # 纯数字/标点
    if re.match(r'^[\d\s.,;:!?？。，、！…~\-—+=\[\]【】()（）#@\$%^&*"\'`/_|\\]+$', text):
        return True

    # 长度 < MIN_CONTENT_LENGTH（中英混合算字数）
    # 中文：1 字 = 1 长度；英文单词/数字串：按字符数
    if len(text) < MIN_CONTENT_LENGTH:
        return True

    return False


# ═══════════════════════════════════════════════
#  活跃度：纯数据驱动（与 v2 一致）
# ═══════════════════════════════════════════════

def calc_active_scores(by_sender: dict, total_days: int) -> dict:
    raw = {}
    for sid, msgs in by_sender.items():
        days_set = set()
        for m in msgs:
            days_set.add(datetime.fromtimestamp(m["sent_at"]).date())
        raw[sid] = {"msg_count": len(msgs), "distinct_days": len(days_set)}

    counts = [r["msg_count"] for r in raw.values()]
    days_list = [r["distinct_days"] for r in raw.values()]
    max_count = max(counts) if counts else 1
    max_days = max(days_list) if days_list else total_days

    scores = {}
    for sid, r in raw.items():
        if max_count > 1:
            msg_norm = math.log(r["msg_count"] + 1) / math.log(max_count + 1)
        else:
            msg_norm = 0
        day_norm = r["distinct_days"] / max(max_days, 1)
        scores[sid] = round(msg_norm * 6 + day_norm * 4, 1)
    return scores


# ═══════════════════════════════════════════════
#  数据抽取 & 清洗 & 分组
# ═══════════════════════════════════════════════

def get_message_dbs():
    decrypt_dir = Path.home() / "wechat-decrypt" / "decrypted" / "message"
    return sorted([
        str(p) for p in decrypt_dir.glob("message_*.db")
        if p.name.startswith("message_") and not p.name.endswith("_fts.db")
    ])

def get_contact_db():
    return Path.home() / "wechat-decrypt" / "decrypted" / "contact" / "contact.db"


def extract_and_clean(days: int):
    """抽取 → 清洗 → 按日期分组 → 返回 {date_str: [clean_msg, ...]}"""
    since_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    message_dbs = get_message_dbs()
    contact_db = get_contact_db()

    print(f"[*] 抽取 {days} 天内消息 ({datetime.fromtimestamp(since_ts).strftime('%m/%d')} ~ "
          f"{datetime.now().strftime('%m/%d')})")
    print(f"[*] 消息 DB: {len(message_dbs)} 个文件")

    messages = extract_messages_for_push(contact_db, message_dbs, TARGET_GROUP, since_ts)
    print(f"[+] 原始消息: {len(messages)} 条")

    # ── 解析显示名 ──
    sender_ids = list(set(m["sender_id"] for m in messages))
    _, contact_by_wxid = build_contact_map(contact_db)
    wxid_map = resolve_sender_wxid(contact_db, message_dbs, TARGET_GROUP, sender_ids)
    display_names = {}
    resolved_wxid = {}
    for sid in sender_ids:
        v = wxid_map.get(sid)
        w = v[0] if isinstance(v, tuple) else v
        resolved_wxid[sid] = w if w else f"unknown_{sid}"
        display_names[sid] = contact_by_wxid.get(w, str(w)) if w else f"u{sid}"

    # ── 清洗 + 按日期分组 ──
    # 同时维护 by_sender（所有消息，用于活跃度计算）
    by_sender_all = defaultdict(list)
    by_date_clean = defaultdict(list)
    filtered_count = 0
    system_count = 0

    for msg in messages:
        sid = msg["sender_id"]
        by_sender_all[sid].append(msg)

        if is_noise(msg["content"]):
            filtered_count += 1
            continue

        date_str = datetime.fromtimestamp(msg["sent_at"]).strftime("%Y-%m-%d")
        content = msg["content"].strip()

        by_date_clean[date_str].append({
            "sender_id": sid,
            "name": display_names.get(sid, f"u{sid}"),
            "time": datetime.fromtimestamp(msg["sent_at"]).strftime("%H:%M"),
            "content": content,
            "sent_at": msg["sent_at"],
        })

    # ── 按时间排序每天的消息 ──
    for date_str in by_date_clean:
        by_date_clean[date_str].sort(key=lambda m: m["sent_at"])

    total_clean = sum(len(v) for v in by_date_clean.values())
    print(f"[+] 过滤: {filtered_count} 条噪音 → 保留 {total_clean} 条")
    print(f"[+] {len(by_sender_all)} 个发言人 | {len(by_date_clean)} 天")

    # ── 大天切分（> MAX_MSG_PER_DAY 则按6h窗口切） ──
    final_chunks = {}
    for date_str, msgs in by_date_clean.items():
        if len(msgs) <= MAX_MSG_PER_DAY:
            final_chunks[date_str] = msgs
        else:
            # 按6小时间隔切分
            windows = defaultdict(list)
            for m in msgs:
                hour_bucket = (datetime.fromtimestamp(m["sent_at"]).hour // 6) * 6
                key = f"{date_str}_{hour_bucket:02d}h"
                windows[key].append(m)
            for key, wmsgs in windows.items():
                final_chunks[key] = wmsgs
            print(f"  ⚠ {date_str}: {len(msgs)} 条 → 切分为 {len(windows)} 个窗口")

    return final_chunks, by_sender_all, display_names, resolved_wxid


# ═══════════════════════════════════════════════
#  AI 评分 Prompt（上下文感知 v3）
# ═══════════════════════════════════════════════

SYSTEM_PROMPT = """你是一个高质量社群的内容评估助手。社群名称：前进四社群（Crypto/Web3 投资研究）。

## 你的任务
阅读下方完整的群聊记录（按时间顺序排列），找出真正有分享价值、研究深度、协作精神的发言，并为每个发言标注贡献类型和质量。

## 贡献类型定义

- **sharer (分享者)**: 分享有价值的信息、数据、工具、链接、见解、一手消息
  - ✅ 例: "刚看到 Binance Research 出了新报告，关于RWA的，链接xxx"
  - ✅ 例: "我整理了一下最近半个月的空投汇总"
  - ❌ 不是: "怎么买"、"跌了没"（这些是求助/闲聊，不算分享）

- **researcher (研究者)**: 深入分析、原创思考、数据支撑、系统性输出、提出新框架
  - ✅ 例: "我来分析一下这个项目的代币经济学，第一解锁时间线是..."
  - ✅ 例: "对比了一下三个L2的TPS数据，Arbitrum在xxx场景下明显优于..."
  - ❌ 不是: 随手转发文章不附评论（那是分享，不是研究）

- **collaborator (协作者)**: 帮助他人解决问题、维护群氛围、协调讨论、管理群秩序
  - ✅ 例: "@新人 你那个问题我之前遇到过，解决方案是..."
  - ✅ 例: 管理员引导话题、制止争吵、欢迎新人
  - ❌ 不是: 普通闲聊互动

## 评分规则

- 质量分 1-10：10=极其有价值（系统性干货/独家信息），5=一般有价值，1=勉强算贡献
- 只有真正有贡献的发言才输出。闲聊、灌水、简单问答（"好"、"谢谢"、"😂" 等）**不要输出**
- 同一个人同一话题的多条消息，合并为一条标注（取最高质量分）
- 一条消息可以同时属于多个类型（如：既有研究深度又帮助了他人 → researcher + collaborator）

## 输出格式

严格输出 JSON array，不要 markdown 包裹，不要额外文字：
[
  {
    "time": "发消息时间 HH:MM",
    "user": "发言人名称",
    "types": ["sharer", "researcher", "collaborator"],
    "value": 8,
    "reason": "为什么算贡献（20字以内）"
  }
]

按时间顺序排列。只输出 JSON。"""


def build_day_prompt(date_label: str, msgs: list) -> str:
    """构建一天的会话 prompt"""
    lines = [f"以下是前进四社群 {date_label} 的群聊记录（已过滤水聊）。\n"]
    for m in msgs:
        lines.append(f"[{m['time']}] {m['name']}: {m['content']}")

    # Token 估算：约 1.5 token/char（中英混合）
    chat_text = "\n".join(lines)
    est_tokens = len(chat_text) * 1.5
    if est_tokens > 60000:
        # 截断警告（DeepSeek context 64K）
        print(f"  ⚠ {date_label}: 预估 {int(est_tokens):,} tokens，可能超限，截取前 60%")
        lines = lines[:int(len(lines) * 0.6)]
        chat_text = "\n".join(lines)

    return chat_text


# ═══════════════════════════════════════════════
#  DeepSeek API 调用（单天）
# ═══════════════════════════════════════════════

def call_deepseek_day(api_key: str, date_label: str, msgs: list) -> dict:
    """对一天/一个窗口的会话进行评分"""
    prompt = build_day_prompt(date_label, msgs)

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }).encode()

    req = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
    )

    resp = urllib.request.urlopen(req, timeout=180)
    result = json.loads(resp.read())
    raw_content = result["choices"][0]["message"]["content"]

    # 解析 JSON（处理可能的 markdown 包裹）
    content = raw_content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

    try:
        contributions = json.loads(content)
    except json.JSONDecodeError:
        print(f"  ⚠ {date_label}: JSON 解析失败，尝试修复...")
        # 尝试提取第一个 [ 到最后一个 ]
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1:
            try:
                contributions = json.loads(content[start:end+1])
            except:
                print(f"  ❌ {date_label}: 无法修复 JSON")
                return {"date": date_label, "contributions": [], "error": "json_parse_failed"}
        else:
            print(f"  ❌ {date_label}: 无 JSON array")
            return {"date": date_label, "contributions": [], "error": "no_json_found"}

    if not isinstance(contributions, list):
        contributions = []

    # 汇总当天每人分数
    daily_scores = defaultdict(lambda: {"sharer": 0, "researcher": 0, "collaborator": 0, "contrib_count": 0})
    for c in contributions:
        user = c.get("user", "")
        types = c.get("types", [])
        value = c.get("value", 0)
        if isinstance(value, str):
            try:
                value = int(value)
            except:
                value = 0

        for t in types:
            if t in ("sharer", "researcher", "collaborator"):
                daily_scores[user][t] += value
        daily_scores[user]["contrib_count"] += 1

    return {
        "date": date_label,
        "contributions": contributions,
        "daily_scores": {k: dict(v) for k, v in daily_scores.items()},
        "msg_count": len(msgs),
        "contrib_count": len(contributions),
    }


# ═══════════════════════════════════════════════
#  并发评分引擎（按天并发）
# ═══════════════════════════════════════════════

def score_all_days(api_key: str, day_chunks: dict, concurrency: int) -> list:
    """并发评分所有天/窗口"""
    items = sorted(day_chunks.items())  # 按日期排序
    total = len(items)
    results = [None] * total
    lock = __import__('threading').Lock()

    def score_one(idx: int, date_label: str, msgs: list):
        start = time.time()
        try:
            result = call_deepseek_day(api_key, date_label, msgs)
            elapsed = time.time() - start
            contribs = len(result.get("contributions", []))
            with lock:
                print(f"  [{idx+1}/{total}] ✅ {date_label}: {len(msgs)}条 → {contribs}条贡献 "
                      f"({elapsed:.1f}s)")
            return idx, result, None
        except Exception as e:
            elapsed = time.time() - start
            with lock:
                print(f"  [{idx+1}/{total}] ❌ {date_label}: {str(e)[:80]} ({elapsed:.1f}s)")
            return idx, {"date": date_label, "contributions": [], "daily_scores": {},
                        "msg_count": len(msgs), "error": str(e)}, str(e)

    print(f"\n=== DeepSeek 按天评分 ({total} 窗口, {concurrency} 并发) ===\n")
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(score_one, i, label, msgs): i
            for i, (label, msgs) in enumerate(items)
        }
        for future in as_completed(futures):
            idx, result, err = future.result()
            results[idx] = result

    elapsed = time.time() - t0
    total_contribs = sum(len(r.get("contributions", [])) for r in results if r)
    total_msgs = sum(r.get("msg_count", 0) for r in results if r)
    errors = sum(1 for r in results if r and r.get("error"))
    print(f"\n[⏱] 耗时 {elapsed:.1f}s — {total_msgs}条 → {total_contribs}条贡献 | {errors} 错误")
    return results


# ═══════════════════════════════════════════════
#  汇总 & 龙珠
# ═══════════════════════════════════════════════

def aggregate_and_nominate(day_results: list, display_names: dict, active_scores: dict):
    """跨天汇总 → 归一化 → 龙珠提名"""
    # 累计每人各维度总分
    totals = defaultdict(lambda: {"sharer": 0, "researcher": 0, "collaborator": 0, "contrib_count": 0})

    for day in day_results:
        for user, scores in day.get("daily_scores", {}).items():
            totals[user]["sharer"] += scores.get("sharer", 0)
            totals[user]["researcher"] += scores.get("researcher", 0)
            totals[user]["collaborator"] += scores.get("collaborator", 0)
            totals[user]["contrib_count"] += scores.get("contrib_count", 0)

    if not totals:
        return {}, []

    # ── 归一化到 0-10 ──
    max_sharer = max(v["sharer"] for v in totals.values()) or 1
    max_researcher = max(v["researcher"] for v in totals.values()) or 1
    max_collaborator = max(v["collaborator"] for v in totals.values()) or 1

    normalized = {}
    for user, raw in totals.items():
        normalized[user] = {
            "sharer": round(raw["sharer"] / max_sharer * 10, 1),
            "researcher": round(raw["researcher"] / max_researcher * 10, 1),
            "collaborator": round(raw["collaborator"] / max_collaborator * 10, 1),
            "raw_sharer": raw["sharer"],
            "raw_researcher": raw["researcher"],
            "raw_collaborator": raw["collaborator"],
            "contrib_count": raw["contrib_count"],
        }

    # ── 龙珠：Top N (sharer + researcher) ──
    ranked = sorted(
        normalized.items(),
        key=lambda x: -(x[1]["sharer"] + x[1]["researcher"])
    )
    dragon_ball_winners = [name for name, _ in ranked[:DRAGON_BALL_COUNT]]

    return normalized, dragon_ball_winners


# ═══════════════════════════════════════════════
#  龙珠颁奖词生成
# ═══════════════════════════════════════════════

DRAGON_REASON_PROMPT = """你是前进四社群的 AI 观察员。以下是本周期龙珠得主的贡献摘要。

龙珠是社群最高荣誉，授予分享价值和研究深度最突出的人。请为每位得主写一句颁奖词（20-40字中文），概括 TA 本周期最亮眼的贡献。

格式（严格 JSON）：
[
  {"name": "得主名", "reason": "一句颁奖词"}
]

只输出 JSON。"""

def generate_dragon_reasons(api_key: str, dragon_winners: list, day_results: list) -> dict:
    """为每位龙珠得主生成颁奖词"""
    # 收集每位得主的贡献
    winner_contribs = defaultdict(list)
    for day in day_results:
        for c in day.get("contributions", []):
            user = c.get("user", "")
            if user in dragon_winners:
                winner_contribs[user].append({
                    "time": c.get("time", ""),
                    "types": c.get("types", []),
                    "reason": c.get("reason", ""),
                    "value": c.get("value", 0),
                })

    if not winner_contribs:
        return {name: "本周期社群贡献突出" for name in dragon_winners}

    # 构建 prompt
    parts = []
    for name, contribs in winner_contribs.items():
        parts.append(f"\n## {name}")
        total = sum(c["value"] for c in contribs)
        parts.append(f"贡献 {len(contribs)} 次，累计价值 {total} 分")
        for c in contribs[:5]:  # 最多5条
            parts.append(f"  - {c['reason']}")

    prompt = DRAGON_REASON_PROMPT + "\n".join(parts)

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "只输出 JSON array，不要 markdown，不要额外文字。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
        "max_tokens": 500,
    }).encode()

    try:
        req = urllib.request.Request(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"].strip()

        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)

        reasons_list = json.loads(content)
        reasons = {}
        for item in reasons_list:
            reasons[item.get("name", "")] = item.get("reason", "社群贡献突出")
        return reasons
    except Exception as e:
        print(f"  ⚠ 颁奖词生成失败: {e}")
        return {name: "本周期社群贡献突出" for name in dragon_winners}


# ═══════════════════════════════════════════════
#  本地保存 & 打印
# ═══════════════════════════════════════════════

def save_and_display(day_results: list, normalized: dict, dragon_winners: list,
                     active_scores: dict, display_names: dict, days: int,
                     all_sender_ids: set, dragon_reasons: dict = None):
    """保存本地 JSON + 打印排行榜"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # 构建反向映射: display_name → sender_id
    name_to_sid = {}
    for sid, name in display_names.items():
        name_to_sid[name] = sid

    # 转换龙珠得主: display_name → sender_id
    dragon_winners_sid = set()
    for name in dragon_winners:
        sid = name_to_sid.get(name)
        if sid:
            dragon_winners_sid.add(sid)

    # ── 保存逐条贡献标注（本地） ──
    detail_path = BASE_DIR / f"scores_v3_detail_{timestamp}.json"
    with open(detail_path, 'w') as f:
        json.dump({
            "analyzed_at": datetime.now().isoformat(),
            "days": days,
            "daily_contributions": [
                {
                    "date": d["date"],
                    "msg_count": d.get("msg_count", 0),
                    "contrib_count": len(d.get("contributions", [])),
                    "contributions": d.get("contributions", []),
                    "error": d.get("error"),
                }
                for d in day_results
            ],
        }, f, ensure_ascii=False, indent=2)

    # ── 合并活跃度 → 总分 ──
    combined = {}
    all_sids_with_ai = set()
    for name in normalized:
        sid = name_to_sid.get(name)
        if sid:
            all_sids_with_ai.add(sid)

    all_sids = all_sids_with_ai | all_sender_ids
    for sid in all_sids:
        name = display_names.get(sid, str(sid))
        active = active_scores.get(sid, 0)
        ai = normalized.get(name, {"sharer": 0, "researcher": 0, "collaborator": 0, "contrib_count": 0})
        total = round(active + ai["sharer"] + ai["researcher"] + ai["collaborator"], 1)
        in_dragon = sid in dragon_winners_sid
        dragon_reason = (dragon_reasons or {}).get(name, "")
        combined[sid] = {
            "name": name,
            "active": active,
            "sharer": ai["sharer"],
            "researcher": ai["researcher"],
            "collaborator": ai["collaborator"],
            "total": total,
            "contrib_count": ai.get("contrib_count", 0),
            "dragon_ball": in_dragon,
            "dragon_reason": dragon_reason if in_dragon else "",
        }

    # ── 保存汇总 ──
    summary_path = BASE_DIR / f"scores_v3_summary_{timestamp}.json"
    scores_latest_path = BASE_DIR / "scores_latest.json"

    # 为 JSON 输出添加 name 字段
    summary_combined = {}
    for sid, s in combined.items():
        summary_combined[s["name"]] = {k: v for k, v in s.items() if k != "name"}
    summary = {
        "analyzed_at": datetime.now().isoformat(),
        "days": days,
        "users": len(combined),
        "dragon_ball_winners": dragon_winners,
        "dragon_ball_count": DRAGON_BALL_COUNT,
        "scores": summary_combined,
    }
    with open(summary_path, 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(scores_latest_path, 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── 打印排行榜 ──
    ranked = sorted(combined.items(), key=lambda x: -x[1]["total"])

    print(f"\n{'='*65}")
    print(f"  🏆 前进四社群 · 积分排行榜 Top 20 ({days}天)")
    print(f"{'='*65}")
    print(f"  {'排名':4s} {'发言人':18s} {'活跃':>5s} {'分享':>5s} {'研究':>5s} {'协作':>5s} {'总分':>6s}")
    print(f"  {'-'*60}")

    for i, (sid, s) in enumerate(ranked[:20]):
        dragon = "🐉" if s["dragon_ball"] else "  "
        name = s["name"]
        print(f"  {dragon} {i+1:2d}. {name[:18]:18s} "
              f"{s['active']:5.1f} {s['sharer']:5.1f} {s['researcher']:5.1f} "
              f"{s['collaborator']:5.1f} {s['total']:6.1f}")

    print(f"\n  🐉 龙珠得主 ({DRAGON_BALL_COUNT} 人):")
    for i, name in enumerate(dragon_winners):
        sid = name_to_sid.get(name)
        stats = combined.get(sid, {})
        reason = stats.get("dragon_reason", "")
        print(f"     {i+1}. {name}  (分享{stats.get('sharer',0):.1f} + 研究{stats.get('researcher',0):.1f})")
        if reason:
            print(f"        💬 {reason}")

    print(f"\n  📁 逐条标注: {detail_path}")
    print(f"  📁 汇总数据: {summary_path}")

    return combined, ranked


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
                    url = url.replace('sslmode=no-verify', 'sslmode=require')
                    return url
    return None


def push_to_supabase(combined: dict, active_scores: dict, display_names: dict,
                     wxid_map: dict, dragon_winners: list):
    """推送评分到 Supabase（累加模式）"""
    import psycopg2

    db_url = read_db_url()
    if not db_url:
        print("[!] 找不到 DATABASE_URL")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    now = datetime.now()
    inserted = 0
    new_users = 0
    backfilled = 0

    for sender_id, scores in combined.items():
        name = scores.get("name", display_names.get(sender_id, f"u{sender_id}"))
        wxid = wxid_map.get(sender_id, f"unknown_{sender_id}")
        active = scores.get("active", 0)
        sharer = scores.get("sharer", 0)
        researcher = scores.get("researcher", 0)
        collaborator = scores.get("collaborator", 0)
        dragon = 1 if scores.get("dragon_ball") else 0
        dragon_reason = scores.get("dragon_reason", "")
        earned_this_run = int(active + sharer + researcher + collaborator)

        # 查找/创建用户（优先按 wxid）
        uid = None
        if wxid and wxid != f"unknown_{sender_id}":
            cur.execute('SELECT id, username FROM users WHERE wxid = %s', (wxid,))
            row = cur.fetchone()
            if row:
                uid = row[0]
                if row[1] != name:
                    cur.execute('UPDATE users SET username = %s, "updatedAt" = %s WHERE id = %s', (name, now, uid))

        if not uid:
            cur.execute('SELECT id, wxid FROM users WHERE username = %s', (name,))
            row = cur.fetchone()
            if row:
                uid = row[0]
                if not row[1]:
                    cur.execute('UPDATE users SET wxid = %s, "updatedAt" = %s WHERE id = %s', (wxid, now, uid))
                    backfilled += 1

        if not uid:
            uid = str(uuid.uuid4())
            code = f"auto-{uuid.uuid4().hex[:8]}"
            cur.execute(
                'INSERT INTO users (id, username, wxid, "inviteCode", "createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, %s)',
                (uid, name, wxid, code, now, now)
            )
            new_users += 1

        # 累加模式：UPDATE totalEarned += 本轮积分，覆盖评分维度
        cur.execute('''
            INSERT INTO scores (id, "userId", "activePoints", "sharerPoints", "researcherPoints",
                                "collaboratorPoints", "dragonBalls", "dragonBallReason",
                                "totalEarned", "totalSpent")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            ON CONFLICT ("userId") DO UPDATE SET
                "activePoints" = EXCLUDED."activePoints",
                "sharerPoints" = EXCLUDED."sharerPoints",
                "researcherPoints" = EXCLUDED."researcherPoints",
                "collaboratorPoints" = EXCLUDED."collaboratorPoints",
                "dragonBalls" = scores."dragonBalls" + EXCLUDED."dragonBalls",
                "dragonBallReason" = EXCLUDED."dragonBallReason",
                "totalEarned" = scores."totalEarned" + %s
        ''', (
            str(uuid.uuid4()), uid,
            active, sharer, researcher, collaborator,
            dragon, dragon_reason,
            earned_this_run,
            earned_this_run,  # For the DO UPDATE SET totalEarned
        ))
        inserted += 1

    conn.commit()

    cur.execute('SELECT COUNT(*), SUM("totalEarned"), SUM("totalSpent") FROM scores')
    cnt, earned, spent = cur.fetchone()
    conn.close()

    print(f"\n✅ Supabase: {cnt} 条评分 | 累计获得 {earned or 0} 分 | 已消费 {spent or 0} 分 | "
          f"新用户 {new_users} | 补填 wxid {backfilled}")


# ═══════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AI 评分引擎 v3：按天全量 + 上下文感知")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # ── 读取 API key ──
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        key_file = Path("/tmp/deepseek_key.bin")
        if key_file.exists():
            with open(key_file, 'rb') as f:
                api_key = f.read().decode().strip()
    if not api_key:
        print("[!] 请设置 DEEPSEEK_API_KEY 或确保 /tmp/deepseek_key.bin 存在")
        sys.exit(1)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  AI 评分引擎 v3 · 按天全量 + 上下文感知                ║")
    print(f"║  清洗: ≥{MIN_CONTENT_LENGTH}字 | 分组: 按天 | 龙珠: Top {DRAGON_BALL_COUNT} (分享+研究) ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"  目标群: {TARGET_GROUP}")
    print(f"  周期: {args.days} 天 | 并发: {args.concurrency}\n")

    # ── Step 1: 抽取 & 清洗 & 分组 ──
    day_chunks, by_sender_all, display_names, wxid_map = extract_and_clean(args.days)
    if not day_chunks:
        print("[!] 无有效消息")
        return

    # ── Step 2: 活跃度 ──
    active_scores = calc_active_scores(by_sender_all, args.days)

    # ── Step 3: AI 评分 ──
    day_results = score_all_days(api_key, day_chunks, args.concurrency)

    # ── Step 4: 汇总 & 龙珠 ──
    normalized, dragon_winners = aggregate_and_nominate(
        day_results, display_names, active_scores
    )

    # ── Step 4.5: 龙珠颁奖词 ──
    print(f"\n=== 生成龙珠颁奖词 ===")
    dragon_reasons = generate_dragon_reasons(api_key, dragon_winners, day_results)
    for name, reason in dragon_reasons.items():
        print(f"  🐉 {name}: {reason}")

    # ── Step 5: 保存 & 展示 ──
    all_sids = set(by_sender_all.keys())
    combined, ranked = save_and_display(
        day_results, normalized, dragon_winners,
        active_scores, display_names, args.days, all_sids, dragon_reasons
    )

    # ── Step 6: Supabase ──
    if not args.dry_run:
        print("\n=== 推送 Supabase ===")
        try:
            push_to_supabase(combined, active_scores, display_names, wxid_map, dragon_winners)
        except Exception as e:
            print(f"[!] Supabase 推送失败: {e}")

    print(f"\n🎉 v3 评分完成！")


if __name__ == "__main__":
    main()

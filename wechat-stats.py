#!/usr/bin/env python3
"""
wechat-stats.py — 微信群聊活跃度分析工具
==========================================
前置依赖: ylytdeng/wechat-decrypt (https://github.com/ylytdeng/wechat-decrypt)
  安装: git clone https://github.com/ylytdeng/wechat-decrypt.git ~/wechat-decrypt

用法:
  python wechat-stats.py                                    # 分析所有群
  python wechat-stats.py --group "群名关键字"                # 筛选群
  python wechat-stats.py --decrypt                          # 先解密再分析
  python wechat-stats.py --set-name "群ID" "显示名"         # 自定义群名
"""

import sys
import os
import json
import hashlib
import re
import sqlite3
import argparse
import subprocess
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = Path(__file__).parent
WECHAT_DECRYPT_DIR = Path(os.environ.get("WECHAT_DECRYPT_DIR", Path.home() / "wechat-decrypt"))

DEFAULT_OUTPUT = BASE_DIR / "wechat-stats.json"
GROUP_NAMES_FILE = BASE_DIR / "group-names.json"


# ============================================================
# 解密（委托给 wechat-decrypt）
# ============================================================
def run_decrypt(wechat_dir):
    """运行 wechat-decrypt 的解密流程"""
    wd = Path(wechat_dir)
    
    # 1. 提取密钥
    keys_file = wd / "all_keys.json"
    if not keys_file.exists():
        extractor = wd / "find_all_keys_macos"
        if not extractor.exists():
            print(f"[!] 找不到 {extractor}")
            print(f"    请先: cd {wd} && cc -O2 -o find_all_keys_macos find_all_keys_macos.c -framework Foundation")
            return False
        
        print("[*] 提取密钥（需要 sudo）...")
        result = subprocess.run(["sudo", str(extractor)], cwd=wd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[!] 密钥提取失败:\n{result.stderr}")
            return False
        print("[+] 密钥提取完成")
    
    # 2. 解密
    decrypt_script = wd / "decrypt_db.py"
    if not decrypt_script.exists():
        print(f"[!] 找不到 {decrypt_script}")
        return False
    
    print("[*] 解密数据库...")
    venv_python = wd / ".venv" / "bin" / "python3"
    python = str(venv_python) if venv_python.exists() else "python3"
    result = subprocess.run([python, str(decrypt_script)], cwd=wd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] 解密失败:\n{result.stderr}")
        return False
    
    print("[+] 解密完成")
    return True


# ============================================================
# 名称映射
# ============================================================
def load_group_names():
    if GROUP_NAMES_FILE.exists():
        try:
            return json.load(open(GROUP_NAMES_FILE))
        except:
            return {}
    return {}


def save_group_name(username, name):
    names = load_group_names()
    names[username] = name
    json.dump(names, open(GROUP_NAMES_FILE, "w"), ensure_ascii=False, indent=2)
    print(f"[+] 群名已保存: {username[:25]}... → {name}")


def build_contact_map(contact_db_path):
    """构建双映射：contact_id → display_name  和  wxid → display_name"""
    conn = sqlite3.connect(str(contact_db_path))
    contact_by_id = {}
    contact_by_wxid = {}
    for row in conn.execute("SELECT id, username, nick_name, remark, alias, encrypt_username FROM contact"):
        cid, username, nick, remark, alias, enc = row
        # 优先级: remark(备注) > nick_name(昵称) > alias(别名) > username
        display = remark or nick or alias or username or f"id:{cid}"
        contact_by_id[cid] = display
        contact_by_wxid[username] = display
        if enc:
            contact_by_wxid[enc] = display
    conn.close()
    return contact_by_id, contact_by_wxid


def extract_group_name(ext_buf):
    """从 ext_buffer protobuf 提取群名，不可靠时返回 None"""
    if not ext_buf:
        return None
    try:
        text = ext_buf.decode('utf-8', errors='replace')
        best = ""
        current = ""
        for ch in text:
            if ch.isprintable() and ch not in '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f':
                current += ch
            else:
                if len(current) > len(best) and any('\u4e00' <= c <= '\u9fff' for c in current):
                    best = current
                current = ""
        if current and len(current) > len(best) and any('\u4e00' <= c <= '\u9fff' for c in current):
            best = current
        
        # 过滤明显的垃圾结果：含有 protobuf 残留字符、过长、或混杂奇怪字符
        if best and len(best) >= 2 and len(best) <= 40:
            # 检查是否像正常中文群名（至少一个中文，没有控制字符）
            if any('\u4e00' <= c <= '\u9fff' for c in best):
                return best
        return None
    except:
        return None


# ============================================================
# 中文词频 & 情感分析辅助
# ============================================================

# 常见中文停用词
STOP_WORDS = set(
    "的了吗嗯哦啊吧呢哈呵呀嗨喂嘿哎哟噢么嘛啦哇嘻咧呐咯喔呗喵咚呃呱呵哒嘞嘞喽噢哟喂嘛"
    "在是和或但就也这那不还只个些所都于及与"
    "你我他她它我们你们他们她们它们自己大家"
    "一个什么怎么怎么样为什么因为所以如果虽然但是然而而且"
    "一下一些一种这个那个这些那些"
    "可以能够应该需要可能已经正在"
    "很非常好比较更最"
    "说看去来做去去想到知道觉得认为"
    "的时候地方里面上面下面"
    "一二是三四五六七八九十百千万亿"
    "上月日年时分钟"
    "有没无被把将以对从到过出了"
    "和跟同与及及其"
    "的之乎者也太"
    "着等"
)

# 情感词典（简易版）
POSITIVE_WORDS = {
    "涨", "赚", "发财", "起飞", "牛逼", "厉害", "稳", "强", "棒", "赞", "👍",
    "不错", "可以", "好的", "漂亮", "优秀", "666", "猛", "香", "爽", "赢",
    "利好", "突破", "新高", "牛市", "抄底", "抄到", "赚了", "涨停", "暴涨",
    "开心", "哈哈", "恭喜", "到位", "精准", "分享", "谢谢", "感谢",
    "给力", "完美", "精彩", "舒服", "刺激", "过瘾", "赞一个", "6666",
    "必胜", "放心", "看好", "坚信", "坚信", "财富", "自由", "密码",
}
NEGATIVE_WORDS = {
    "跌", "亏", "亏了", "惨", "垃圾", "烂", "差", "坑", "割", "套", "💩",
    "没了", "不行", "糟糕", "完蛋", "崩", "瀑布", "归零", "骗", "局",
    "跌停", "暴跌", "血亏", "难受", "蛋疼", "坑爹", "恶心", "跑路",
    "崩了", "塌了", "腰斩", "爆仓", "清仓", "割肉", "止损", "追高",
    "被骗", "传销", "空气", "归零", "归零了",
}


def tokenize_chinese(text):
    """简易中文分词：按标点/空格切分后，提取 2-4 字词组"""
    import re
    # 移除 URL、@提及、纯数字/符号
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'@\S+', '', text)
    text = re.sub(r'[a-zA-Z0-9]+', '', text)  # 英文/数字暂不统计
    # 按标点切分
    segments = re.split(r'[，。！？、；：\s\n\r,\.!\?;:\'\"()\[\]{}【】《》\u2000-\u206f]+', text)

    words = []
    for seg in segments:
        seg = seg.strip()
        if len(seg) < 2:
            continue
        # 生成 2-gram, 3-gram, 4-gram
        for n in range(2, min(5, len(seg) + 1)):
            for i in range(len(seg) - n + 1):
                word = seg[i:i + n]
                # 过滤：不含字母数字，非纯标点，不在停用词中
                if not any(c in STOP_WORDS for c in word):
                    if all('\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' for c in word):
                        words.append(word)
    return words


def analyze_sentiment(texts):
    """返回情感分数：-1~1"""
    if not texts:
        return 0.0
    pos_count = 0
    neg_count = 0
    total_sentiment_msgs = 0
    for text in texts:
        has_pos = any(w in text for w in POSITIVE_WORDS)
        has_neg = any(w in text for w in NEGATIVE_WORDS)
        if has_pos or has_neg:
            total_sentiment_msgs += 1
            if has_pos:
                pos_count += 1
            if has_neg:
                neg_count += 1
    if total_sentiment_msgs == 0:
        return 0.0
    return (pos_count - neg_count) / (pos_count + neg_count)


def extract_keywords(texts, top_n=80):
    """从消息文本中提取关键词频率"""
    from collections import Counter
    counter = Counter()
    for text in texts:
        words = tokenize_chinese(text)
        counter.update(words)
    # 过滤低频词
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n) if c >= 2]


# ============================================================
# 核心分析
# ============================================================
def analyze_group(contact_db_path, message_dbs, group_username, room_id, contact_by_id, contact_by_wxid, detailed=False):
    md5 = hashlib.md5(group_username.encode()).hexdigest()
    table_name = f"Msg_{md5}"

    conn_contact = sqlite3.connect(str(contact_db_path))
    row = conn_contact.execute(
        "SELECT ext_buffer FROM chat_room WHERE username=?", (group_username,)
    ).fetchone()
    ext_buf = row[0] if row else None
    custom_names = load_group_names()
    if group_username in custom_names:
        group_name = custom_names[group_username]
    else:
        # ext_buffer 取群名不可靠（经常取到成员昵称），直接不取
        cnt = conn_contact.execute(
            "SELECT COUNT(*) FROM chatroom_member WHERE room_id=?", (room_id,)
        ).fetchone()[0]
        group_name = f"群聊 ({cnt}人)"

    members = conn_contact.execute(
        "SELECT member_id FROM chatroom_member WHERE room_id=?", (room_id,)
    ).fetchall()
    member_ids = set(r[0] for r in members)
    conn_contact.close()

    now = datetime.now()
    cutoffs = {
        "1month": int((now - timedelta(days=30)).timestamp()),
        "3month": int((now - timedelta(days=90)).timestamp()),
        "6month": int((now - timedelta(days=180)).timestamp()),
    }

    # 从消息字段提取 real_sender_id → wxid 映射
    # wxid 存在于 message_content 明文（text 消息的 "wxid_xxx:\n内容" 格式）
    # 或 source 字段的 Latin-1 解码中
    sender_wxid = {}
    for msg_db_path in message_dbs:
        conn = sqlite3.connect(str(msg_db_path))
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        if exists:
            sids = conn.execute(f"SELECT DISTINCT real_sender_id FROM [{table_name}]").fetchall()
            for (sid,) in sids:
                if sid in sender_wxid:
                    continue
                # 1) 尝试 message_content（明文，跳过 WCDB 压缩行）
                row = conn.execute(
                    f"SELECT message_content FROM [{table_name}] WHERE real_sender_id=? AND message_content IS NOT NULL AND message_content != '' AND (WCDB_CT_message_content IS NULL OR WCDB_CT_message_content = 0) LIMIT 1",
                    (sid,)
                ).fetchone()
                if row and row[0]:
                    text = row[0] if isinstance(row[0], str) else row[0].decode('utf-8', errors='replace')
                    # wxid_xxx:\n 格式
                    m = re.match(r'(wxid_[a-zA-Z0-9]+):\n', text)
                    if m:
                        sender_wxid[sid] = m.group(1)
                        continue
                    # 普通微信号:\n 格式
                    m = re.match(r'([a-zA-Z][a-zA-Z0-9_]{4,30}):\n', text)
                    if m and m.group(1) not in ('https', 'http', 'www'):
                        sender_wxid[sid] = m.group(1)
                        continue
                
                # 2) 尝试 source 字段（protobuf, Latin-1 解码后搜索）
                row = conn.execute(
                    f"SELECT source FROM [{table_name}] WHERE real_sender_id=? AND source IS NOT NULL LIMIT 1",
                    (sid,)
                ).fetchone()
                if row and row[0]:
                    data = row[0] if isinstance(row[0], bytes) else row[0].encode('latin-1')
                    text = data.decode('latin-1', errors='replace')
                    m = re.search(r'([a-zA-Z][a-zA-Z0-9_]{4,30}):\n', text)
                    if m and m.group(1) not in ('https', 'http', 'www', 'com'):
                        sender_wxid[sid] = m.group(1)
                        continue
        conn.close()

    sender_stats = defaultdict(lambda: {
        "total": 0, "1month": 0, "3month": 0, "6month": 0,
        "first_msg": None, "last_msg": None
    })

    for msg_db_path in message_dbs:
        conn = sqlite3.connect(str(msg_db_path))
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        if exists:
            for sender_id, create_time in conn.execute(
                f"SELECT real_sender_id, create_time FROM [{table_name}]"
            ).fetchall():
                s = sender_stats[sender_id]
                s["total"] += 1
                for period, cutoff in cutoffs.items():
                    if create_time >= cutoff:
                        s[period] += 1
                if s["first_msg"] is None or create_time < s["first_msg"]:
                    s["first_msg"] = create_time
                if s["last_msg"] is None or create_time > s["last_msg"]:
                    s["last_msg"] = create_time
        conn.close()

    # 整合：遍历所有群成员，通过 wxid 匹配消息统计
    # 群成员 member_id → contact_by_id → wxid → contact_by_wxid
    conn_contact = sqlite3.connect(str(contact_db_path))
    member_wxid = {}
    for mid in member_ids:
        wxid = conn_contact.execute("SELECT username FROM contact WHERE id=?", (mid,)).fetchone()
        if wxid:
            member_wxid[mid] = wxid[0]
    conn_contact.close()

    # 建立 wxid → sender_stats 的映射（通过 sender_wxid 中转）
    wxid_stats = {}
    for sid, stats in sender_stats.items():
        wxid = sender_wxid.get(sid)
        if wxid:
            wxid_stats[wxid] = stats
    
    members_list = []
    total_messages = 0
    for mid in member_ids:
        wxid = member_wxid.get(mid, "")
        # 通过 wxid 匹配消息统计
        stats = wxid_stats.get(wxid, {"total": 0, "1month": 0, "3month": 0, "6month": 0, "first_msg": None, "last_msg": None})
        display = contact_by_id.get(mid, contact_by_wxid.get(wxid, f"id:{mid}"))

        if stats["1month"] >= 20:
            tag = "🔥超活跃"
        elif stats["1month"] >= 5:
            tag = "🟢活跃"
        elif stats["3month"] >= 5:
            tag = "🟡偶尔"
        elif stats["6month"] > 0:
            tag = "🟠低频"
        elif stats["total"] > 0:
            tag = "🔴沉水"
        else:
            tag = "💀死号"

        members_list.append({
            "name": display,
            "total": stats["total"],
            "last_1month": stats["1month"],
            "last_3month": stats["3month"],
            "last_6month": stats["6month"],
            "tag": tag,
            "first_seen": datetime.fromtimestamp(stats["first_msg"]).strftime("%Y-%m-%d") if stats.get("first_msg") else None,
            "last_seen": datetime.fromtimestamp(stats["last_msg"]).strftime("%Y-%m-%d") if stats.get("last_msg") else None,
        })
        total_messages += stats["total"]

    members_list.sort(key=lambda x: x["total"], reverse=True)

    return {
        "name": group_name,
        "username": group_username,
        "total_members": len(member_ids),
        "total_messages": total_messages,
        "active_1month": sum(1 for m in members_list if m["last_1month"] > 0),
        "active_3month": sum(1 for m in members_list if m["last_3month"] > 0),
        "active_6month": sum(1 for m in members_list if m["last_6month"] > 0),
        "never_spoken": sum(1 for m in members_list if m["total"] == 0),
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "top_20": members_list[:20],
        "all_members": members_list,
    }


# ============================================================
# 推送消息到云端 API（--push 模式）
# ============================================================
SYNC_STATE_FILE = BASE_DIR / ".sync-state.json"

def load_sync_state():
    """加载上次同步时间"""
    if SYNC_STATE_FILE.exists():
        try:
            return json.loads(SYNC_STATE_FILE.read_text())
        except:
            pass
    return {}

def save_sync_state(state):
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))

def extract_messages_for_push(contact_db_path, message_dbs, group_username, since_ts=0):
    """提取消息全文用于推送，跳过 WCDB 压缩行"""
    md5 = hashlib.md5(group_username.encode()).hexdigest()
    table_name = f"Msg_{md5}"
    messages = []

    for msg_db_path in message_dbs:
        conn = sqlite3.connect(str(msg_db_path))
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        if not exists:
            conn.close()
            continue

        # 只取明文消息 + 时间戳过滤
        rows = conn.execute(
            f"""SELECT real_sender_id, message_content, create_time
                FROM [{table_name}]
                WHERE message_content IS NOT NULL
                  AND message_content != ''
                  AND (WCDB_CT_message_content IS NULL OR WCDB_CT_message_content = 0)
                  AND create_time > ?
                ORDER BY create_time ASC""",
            (since_ts,)
        ).fetchall()

        for sender_id, content_raw, create_time in rows:
            content = content_raw if isinstance(content_raw, str) else content_raw.decode('utf-8', errors='replace')
            messages.append({
                "sender_id": sender_id,
                "content": content[:2000],  # 截断过长消息
                "sent_at": create_time,
            })

        conn.close()

    return messages

def resolve_sender_wxid(contact_db_path, message_dbs, group_username, sender_ids):
    """把 sender_id 转成 wxid"""
    md5 = hashlib.md5(group_username.encode()).hexdigest()
    table_name = f"Msg_{md5}"
    result = {}

    for msg_db_path in message_dbs:
        conn = sqlite3.connect(str(msg_db_path))
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        if not exists:
            conn.close()
            continue

        for sid in sender_ids:
            if sid in result:
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
                    result[sid] = m.group(1)
        conn.close()

    return result

def push_to_api(api_url, api_key, group_wxid, messages):
    """POST 消息到 API"""
    import urllib.request as ur

    payload = json.dumps({
        "groupWxId": group_wxid,
        "messages": messages
    }).encode("utf-8")

    req = ur.Request(
        f"{api_url}/api/messages/sync",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )

    try:
        with ur.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run_push(group_username, api_url, api_key, message_dbs, contact_db_path):
    """执行推送：提取 → 转 wxid → 分批 POST"""
    state = load_sync_state()
    since_ts = state.get(group_username, 0)

    print(f"[*] 提取新消息（since {datetime.fromtimestamp(since_ts).isoformat() if since_ts else 'beginning'}）...")

    raw_messages = extract_messages_for_push(contact_db_path, message_dbs, group_username, since_ts)

    if not raw_messages:
        print("[*] 没有新消息")
        return

    # 解析 wxid
    sender_ids = set(m["sender_id"] for m in raw_messages)
    wxid_map = resolve_sender_wxid(contact_db_path, message_dbs, group_username, sender_ids)

    # 组装
    formatted = []
    max_ts = since_ts
    for m in raw_messages:
        wxid = wxid_map.get(m["sender_id"], f"unknown_{m['sender_id']}")
        formatted.append({
            "sender_wxid": wxid,
            "content": m["content"],
            "sent_at": m["sent_at"],
        })
        if m["sent_at"] > max_ts:
            max_ts = m["sent_at"]

    # 分批 POST（每批 200 条）
    batch_size = 200
    total_inserted = 0
    total_skipped = 0

    for i in range(0, len(formatted), batch_size):
        batch = formatted[i:i + batch_size]
        result = push_to_api(api_url, api_key, group_username, batch)
        if result.get("ok"):
            total_inserted += result.get("inserted", 0)
            total_skipped += result.get("skipped", 0)
            print(f"  [{i//batch_size + 1}] +{result.get('inserted', 0)} inserted, {result.get('skipped', 0)} skipped")
        else:
            print(f"  [{i//batch_size + 1}] 失败: {result.get('error', 'unknown')}")
            return

    # 更新同步时间
    state[group_username] = max_ts
    save_sync_state(state)
    print(f"[+] 推送完成: {total_inserted} 新增, {total_skipped} 跳过, 同步到 {datetime.fromtimestamp(max_ts).isoformat()}")

# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="微信群聊活跃度分析工具")
    parser.add_argument("--group", type=str, help="群名/群ID筛选（模糊匹配）")
    parser.add_argument("--set-name", nargs=2, metavar=("USERNAME", "NAME"), help="给群设置自定义显示名")
    parser.add_argument("--decrypt", action="store_true", help="先解密数据库（需 wechat-decrypt 已安装）")
    parser.add_argument("--push", action="store_true", help="推送消息到云端 API（需设置 SYNC_API_URL + SYNC_API_KEY）")
    parser.add_argument("--sync-api-url", type=str, help="推送目标 API 地址（默认读环境变量 SYNC_API_URL）")
    parser.add_argument("--sync-api-key", type=str, help="推送 API Key（默认读环境变量 SYNC_API_KEY）")
    parser.add_argument("--wechat-decrypt-dir", type=str, help=f"wechat-decrypt 安装目录（默认 {WECHAT_DECRYPT_DIR}）")
    parser.add_argument("--decrypted-dir", type=str, help="解密数据库目录（默认 {WECHAT_DECRYPT_DIR}/decrypted）")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help=f"输出JSON文件（默认 {DEFAULT_OUTPUT}）")
    args = parser.parse_args()

    # --set-name
    if args.set_name:
        save_group_name(args.set_name[0], args.set_name[1])
        sys.exit(0)

    # wechat-decrypt 目录
    wechat_dir = Path(args.wechat_decrypt_dir) if args.wechat_decrypt_dir else WECHAT_DECRYPT_DIR

    # 解密
    if args.decrypt:
        if not run_decrypt(wechat_dir):
            sys.exit(1)

    # 找到解密数据库
    if args.decrypted_dir:
        decrypted_dir = Path(args.decrypted_dir)
    else:
        decrypted_dir = wechat_dir / "decrypted"

    if not decrypted_dir.is_dir():
        print(f"[!] 找不到解密数据库目录: {decrypted_dir}")
        print("    请先运行: python wechat-stats.py --decrypt")
        print(f"    或确认 wechat-decrypt 安装在: {wechat_dir}")
        sys.exit(1)

    contact_db = decrypted_dir / "contact" / "contact.db"
    if not contact_db.exists():
        print(f"[!] 找不到 {contact_db}")
        print("    请先解密数据库: python wechat-stats.py --decrypt")
        sys.exit(1)

    message_dbs = list(decrypted_dir.glob("message/message_*.db"))
    if not message_dbs:
        print(f"[!] 找不到消息数据库")
        sys.exit(1)

    # ─── Push 模式：推送消息到云端 API ───
    if args.push:
        if not args.group:
            print("[!] --push 需要指定 --group")
            sys.exit(1)

        api_url = args.sync_api_url or os.environ.get("SYNC_API_URL", "")
        api_key = args.sync_api_key or os.environ.get("SYNC_API_KEY", "")

        if not api_url or not api_key:
            print("[!] 请设置 SYNC_API_URL 和 SYNC_API_KEY 环境变量")
            print("    或通过 --sync-api-url / --sync-api-key 参数传入")
            sys.exit(1)

        # 找到匹配的群
        keyword = args.group.lower()
        conn = sqlite3.connect(str(contact_db))
        groups_list = conn.execute("SELECT id, username FROM chat_room WHERE username LIKE '%@chatroom'").fetchall()
        matched = None
        for room_id, username in groups_list:
            if keyword in username.lower():
                matched = username
                break
        conn.close()

        if not matched:
            # 尝试通过自定义名匹配
            custom_names = load_group_names()
            for room_id, username in groups_list:
                gname = custom_names.get(username, "")
                if keyword in gname.lower():
                    matched = username
                    break

        if not matched:
            print(f"[!] 找不到群: {args.group}")
            sys.exit(1)

        run_push(matched, api_url, api_key, message_dbs, str(contact_db))
        sys.exit(0)
    # ─── End Push ───

    contact_by_id, contact_by_wxid = build_contact_map(str(contact_db))

    conn = sqlite3.connect(str(contact_db))
    groups = conn.execute("SELECT id, username FROM chat_room WHERE username LIKE '%@chatroom'").fetchall()
    conn.close()

    if not groups:
        print("[!] 没有找到群聊数据")
        sys.exit(1)

    print(f"找到 {len(groups)} 个群聊")

    # 筛选
    if args.group:
        keyword = args.group.lower()
        custom_names = load_group_names()
        matched = []
        conn = sqlite3.connect(str(contact_db))
        for room_id, username in groups:
            row = conn.execute("SELECT ext_buffer FROM chat_room WHERE username=?", (username,)).fetchone()
            gname = custom_names.get(username) or f"群聊 ({username[:10]}...)"
            if keyword in gname.lower() or keyword in username.lower():
                matched.append((room_id, username, gname))
                print(f"  ✓ {gname} ({username[:20]}...)")
        conn.close()

        if not matched:
            print(f"[!] 没有匹配 '{args.group}'，可用群：")
            conn = sqlite3.connect(str(contact_db))
            for room_id, username in groups:
                row = conn.execute("SELECT ext_buffer FROM chat_room WHERE username=?", (username,)).fetchone()
                gname = extract_group_name(row[0]) if row and row[0] else None
                cnt = conn.execute("SELECT COUNT(*) FROM chatroom_member WHERE room_id=?", (room_id,)).fetchone()[0]
                gname = gname or f"群聊 ({cnt}人)"
                print(f"  - {gname[:30]:30s} ({cnt}人, {username[:20]}...)")
            conn.close()
            sys.exit(1)
        groups = matched
    else:
        custom_names = load_group_names()
        conn = sqlite3.connect(str(contact_db))
        for room_id, username in groups:
            row = conn.execute("SELECT ext_buffer FROM chat_room WHERE username=?", (username,)).fetchone()
            gname = custom_names.get(username) or username[:20] + "..."
            print(f"  - {gname[:30]:30s} ({username[:20]}...)")
        conn.close()

    # 分析
    results = []
    for item in groups:
        if len(item) == 3:
            room_id, username, _ = item
        else:
            room_id, username = item
        print(f"\n[*] 分析: {username[:25]}...")
        results.append(analyze_group(str(contact_db), message_dbs, username, room_id, contact_by_id, contact_by_wxid))

    output_path = Path(args.output)
    json.dump({"generated_at": datetime.now().isoformat(), "groups": results},
              open(output_path, "w"), ensure_ascii=False, indent=2)

    print(f"\n[+] 分析完成 → {output_path}")
    port = os.environ.get("PORT", "9090")
    print(f"    Dashboard: http://localhost:{port}/dashboard.html")


if __name__ == "__main__":
    main()

---
name: wechat-group-stats
description: "Use when user wants to analyze WeChat group member activity — count messages per member, rank by recent activity, identify inactive members to remove, or build an activity dashboard. Covers full pipeline: decrypt local WeChat DB → extract group member stats → launch web dashboard."
version: 1.0.0
author: punk2898
license: MIT
metadata:
  hermes:
    tags: [wechat, analytics, dashboard, group-chat, activity]
    related_skills: [skill-creation-methodology]
---

# WeChat Group Activity Stats

## Overview

Extracts group chat activity from WeChat's local encrypted SQLite database on macOS. Gives you: per-member message counts (total / 1mo / 3mo / 6mo), activity tags (🔥超活跃 → 💀死号), an interactive dark-themed web dashboard, and a JSON API for automation.

The full pipeline: decrypt → analyze → dashboard. Agent guides the user through each step, handling platform quirks and permissions.

**Prerequisites:** macOS, WeChat 4.x installed, admin password (sudo).

**Tool directory:** `~/wechat-group-stats/` (this project — contains `wechat-stats.py`, `dashboard.html`, `wechat-server.py`). The upstream decryption engine (`ylytdeng/wechat-decrypt`) should be installed separately at `~/wechat-decrypt/`.

## When to Use

- User says: "analyze my WeChat group activity", "check who's active in my group", "WeChat group stats"
- User wants to identify inactive members to remove
- User wants a recurring activity dashboard
- User asks about setting up WeChat DB decryption for analytics

## Quick Start (for the Agent)

When the user asks to analyze a WeChat group, guide them through this sequence:

### 1. Check Prerequisites

```bash
# Verify WeChat is installed
ls /Applications/WeChat.app

# Check if wechat-decrypt is already set up (external dependency)
ls ~/wechat-decrypt/find_all_keys_macos ~/wechat-decrypt/decrypt_db.py

# Check if this project is cloned
ls ~/wechat-group-stats/wechat-stats.py
```

If wechat-decrypt isn't set up, clone and install:

```bash
git clone https://github.com/ylytdeng/wechat-decrypt.git ~/wechat-decrypt
cd ~/wechat-decrypt
python3 -m venv .venv && source .venv/bin/activate
pip install pycryptodome zstandard pilk tqdm
cc -O2 -o find_all_keys_macos find_all_keys_macos.c -framework Foundation
```

If wechat-group-stats isn't cloned:

```bash
git clone <repo-url> ~/wechat-group-stats
```

### 2. Re-sign WeChat (one-time)

WeChat's Hardened Runtime prevents memory access. Re-signing removes it.

Ask the user to **quit WeChat first**, then run:

```bash
killall WeChat
sudo codesign --force --sign - /Applications/WeChat.app
```

**If codesign fails** with "Operation not permitted":
- Grant Terminal **Full Disk Access** in 系统设置 → 隐私与安全性 → 完全磁盘访问
- Re-open Terminal and retry
- Alternative: `cp -R /Applications/WeChat.app ~/Desktop/ && sign the copy`

Verify: `codesign -dv /Applications/WeChat.app 2>&1 | grep flags` should show `flags=0x2(adhoc)`.

Then ask user to **re-open WeChat and log in**.

### 3. Extract Keys

```bash
cd ~/wechat-decrypt
sudo ./find_all_keys_macos
```

Outputs `all_keys.json`. If it fails with `task_for_pid: 5`, the re-sign in step 2 didn't work — go back.

### 4. Decrypt Database

Auto-detects the `db_storage` path and creates `config.json`:

```bash
cd ~/wechat-decrypt && source .venv/bin/activate
python3 decrypt_db.py
```

Decrypted DBs land in `~/wechat-decrypt/decrypted/`.

### 5. Set Custom Group Name (one-time)

```bash
python3 wechat-stats.py --set-name "群ID" "自定义群名"
# Example:
python3 wechat-stats.py --set-name "45379818937@chatroom" "链上前进四🚀"
```

### 6. Run Analysis

```bash
python3 wechat-stats.py --group "链上前进四" --decrypted-dir ./decrypted
```

Outputs `wechat-stats.json`. If the group name isn't found, run without `--group` to list all groups, then pick the right one.

### 7. Launch Dashboard

```bash
python3 wechat-server.py
# Opens at http://localhost:8080/dashboard.html
```

Dashboard features: member ranking, sortable columns, activity distribution bars, 🔄 one-click refresh button, search filter, tab to toggle active/inactive members.

## Database Schema Reference

> Full details in `references/wechat-db-schema.md` — includes the critical `real_sender_id` → wxid mapping chain discovered 2025-06-03, and why ext_buffer should NOT be used for group names.

Useful for custom queries beyond the built-in analysis:

| Table | Location | Key fields |
|-------|----------|------------|
| `Msg_<md5>` | `message/message_0.db` | `real_sender_id`, `create_time`, `source`, `message_content` |
| `SessionTable` | `session/session.db` | `username` (groups end with `@chatroom`), `summary` |
| `chat_room` | `contact/contact.db` | `username`, `ext_buffer` (protobuf: member list — **NOT group name**) |
| `chatroom_member` | `contact/contact.db` | `room_id`, `member_id` → maps to `contact.id` |
| `contact` | `contact/contact.db` | `id`, `username`, `nick_name`, `remark`, `alias` |

Mapping chain: `Msg_<md5>.real_sender_id` → extract wxid from `message_content` → `contact.username` → `contact.nick_name`/`remark`

**Msg table hash:** `md5(group_username.encode()).hexdigest()`

**Data path (WeChat 4.x):**
```
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/
  xwechat_files/<wxid>/db_storage/{message,contact,session}/*.db
```

## WeChat Encryption Parameters (4.x)

| Parameter | Value |
|-----------|-------|
| SQLCipher version | 4 |
| Page size | 4096 |
| Reserve size | 80 (IV 16 + HMAC-SHA512 64) |
| KDF iterations | 256,000 |
| KDF algorithm | PBKDF2-HMAC-SHA512 |
| HMAC | SHA-512 (64 bytes) |

## Common Pitfalls

1. **`real_sender_id` ≠ `contact.id`**. The message table uses an internal sender ID space that does NOT match `contact.id` or `chatroom_member.member_id`. Must extract wxid from `message_content` (e.g. `"wxid_xxx:\n内容"`) and match against `contact.username`. See `references/wechat-db-schema.md` for the full mapping chain and extraction code.

2. **Display name priority**: `remark(备注) > nick_name(昵称) > alias(别名) > username`. Using `alias > nick` will show machine names like "XYiDao" instead of human names like "毅". For example: contact with `alias="XYiDao", nick="毅"` should display as "毅", not "XYiDao".

3. **WeChat wasn't quit before re-signing.** Running binary/dylib files are locked — codesign fails. Always `killall WeChat` first. Common error: `internal error in Code Signing subsystem / In subcomponent: ...libEGL.dylib`.

4. **Re-signing needs "Full Disk Access" for Terminal.** If `sudo codesign` fails with `Operation not permitted / In subcomponent: ...WeChatAppEx.app`, Terminal.app lacks FDA. Go to 系统设置 → 隐私与安全性 → 完全磁盘访问, add Terminal.app, then **re-open Terminal** and retry.

5. **`--deep` flag causes nested bundle failures.** WeChat.app contains `WeChatAppEx.app` inside — `--deep` tries to recursively sign it and fails with `Operation not permitted`. Use `codesign --force --sign -` without `--deep`. Only the main bundle needs signing to unlock `task_for_pid`. If signing in `/Applications` still fails even with FDA (some macOS versions block writes there regardless), copy WeChat to Desktop first: `cp -R /Applications/WeChat.app ~/Desktop/WeChat_signed.app && sudo codesign --force --sign - ~/Desktop/WeChat_signed.app`, then run the signed copy.

6. **Key extraction needs WeChat running and ad-hoc signed.** The C scanner (`find_all_keys_macos`) reads WeChat's process memory via `mach_vm` — this is blocked by Hardened Runtime (flags=0x10000). Error: `task_for_pid failed: 5`.

7. **WeChat updates will overwrite the ad-hoc signature.** After a WeChat auto-update, you need to re-sign again and re-extract keys. The database encryption key may also change.

8. **Group names not stored locally in WeChat 4.x.** The `ext_buffer` protobuf in `chat_room` contains member info but the group display name is fetched from the server and may not be in the local DB. **Do NOT attempt to extract group names from `ext_buffer`** — the protobuf's first Chinese string is typically a member's nickname (e.g. "秋刀鱼配柠檬"), not the group name. Use `--set-name` to assign custom names stored in `group-names.json`. Without a custom name, display as `"群聊 (X人)"` where X is the member count. The `extract_group_name()` function in wechat-stats.py is intentionally disabled and returns `None`.

9. **Analysis script reads already-decrypted DBs.** After initial setup, daily refreshes only need step 6 (no sudo, no WeChat restart). Only re-run steps 3-4 if WeChat updated or you suspect key changes.

10. **Dashboard needs HTTP server.** Opening `dashboard.html` directly from filesystem will fail to load `wechat-stats.json` due to CORS. Always use `python3 wechat-server.py` or `python3 -m http.server 8080`. The dedicated server also provides the `/api/run` endpoint for the one-click refresh button.

11. **WCDB compression in `message_content`**. The WeChat message DB uses WCDB compression. About 30% of rows have `WCDB_CT_message_content` set to a non-zero value (typically 4), meaning `message_content` contains compressed binary — not readable text. When extracting wxid from `message_content`, always filter: `AND (WCDB_CT_message_content IS NULL OR WCDB_CT_message_content = 0)`. Without this filter, `LIMIT 1` has a ~30% chance of returning binary garbage, causing the wxid mapping to fail silently and the member's message count to stay at 0 (tagged as 💀死号). This can affect 60+ members in a large group. SQLite's `LIKE` operator triggers automatic decompression, so `WHERE message_content LIKE '%wxid_%'` would work too, but `WCDB_CT_message_content = 0` is more explicit and avoids false matches.

## Publishing to GitHub (Privacy Sanitization)

If publishing a fork with these tools, ensure no private data leaks:

- **`.gitignore` must cover**: `wechat-stats.json` (member names + stats), `group-names.json` (group ID mapping), `all_keys.json` (encryption keys), `config.json` (local paths), `.venv/`, `decrypted/`, `wechat_files/`.
- **Remove hardcoded group IDs**: `wechat-server.py` uses `WECHAT_GROUP_ID` env var and `--group=` CLI arg. `dashboard.html` derives the group from loaded JSON data. No group IDs in committed source.
- **Provide example files**: `group-names.example.json` with placeholder values like `"YOUR_GROUP_ID@chatroom": "你的群名"`.
- **README use placeholders**: Replace real group IDs with `你的群ID@chatroom` in documentation examples.

## Verification Checklist

- [ ] `codesign -dv /Applications/WeChat.app` shows `flags=0x2(adhoc)`
- [ ] `sudo ./find_all_keys_macos` produced `all_keys.json` (no `task_for_pid` error)
- [ ] `python3 decrypt_db.py` succeeded: 17/17 or similar, no failures
- [ ] `python3 wechat-stats.py --group "group_keyword"` produced valid JSON
- [ ] `http://localhost:8080/dashboard.html` loads and shows member table
- [ ] 🔄 refresh button works without errors

## After Setup: Daily Use

Once everything is configured, the daily workflow is:

```bash
cd ~/wechat-group-stats
python3 wechat-server.py
# → open http://localhost:8080/dashboard.html
# → click 🔄 刷新分析 anytime
```

No sudo, no WeChat restart, no key extraction — just one command + one click.

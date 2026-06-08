#!/bin/bash
# 微信消息同步脚本 — 由 Hermes cron 调用
# 用法: bash sync.sh
# 环境变量: SYNC_API_URL, SYNC_API_KEY, WECHAT_GROUP (可选)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GROUP="${WECHAT_GROUP:-链上前进四}"

cd "$SCRIPT_DIR"

# 先解密最新数据，再推送
python3 wechat-stats.py --decrypt --push --group "$GROUP" 2>&1

module.exports = {
  apps: [{
    name: 'wechat-dashboard',
    script: 'wechat-server.py',
    interpreter: 'python3',
    cwd: '/Users/allen/wechat-group-stats',
    args: '--port=9090 --group=链上前进四🚀',
    env: {
      WECHAT_DECRYPT_DIR: '/Users/allen/wechat-decrypt',
      WECHAT_GROUP_ID: '链上前进四🚀',
    },
    // Logs
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    error_file: '/Users/allen/wechat-group-stats/logs/error.log',
    out_file: '/Users/allen/wechat-group-stats/logs/out.log',
    // Auto-restart if crashes
    autorestart: true,
    max_restarts: 10,
    restart_delay: 5000,
    // Don't restart if it exits cleanly within 1s
    min_uptime: '10s',
    max_memory_restart: '200M',
  }]
};

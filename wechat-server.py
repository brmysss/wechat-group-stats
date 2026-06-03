#!/usr/bin/env python3
"""
wechat-server.py — 本地 Dashboard 服务
用法:
  python3 wechat-server.py [--port=8080] [--group=群ID]
"""
import http.server
import subprocess
import json
import sys
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).parent
STATS_SCRIPT = BASE_DIR / "wechat-stats.py"
WECHAT_DECRYPT_DIR = Path(os.environ.get("WECHAT_DECRYPT_DIR", Path.home() / "wechat-decrypt"))
GROUP_ARG = os.environ.get("WECHAT_GROUP_ID", "")


class Handler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/run":
            return self._api_run(parsed)
        if parsed.path == "/api/status":
            return self._api_status()

        return super().do_GET()

    def _api_run(self, parsed):
        params = parse_qs(parsed.query)
        group = params.get("group", [GROUP_ARG])[0]
        decrypt = params.get("decrypt", ["0"])[0] == "1"

        cmd = [sys.executable, str(STATS_SCRIPT),
               "--group", group,
               "--decrypted-dir", str(WECHAT_DECRYPT_DIR / "decrypted"),
               "--output", str(BASE_DIR / "wechat-stats.json")]
        if decrypt:
            cmd += ["--decrypt", "--wechat-decrypt-dir", str(WECHAT_DECRYPT_DIR)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(BASE_DIR))
            resp = {"ok": result.returncode == 0, "output": result.stdout[-500:], "error": result.stderr[-500:]}
            code = 200 if result.returncode == 0 else 500
        except subprocess.TimeoutExpired:
            resp = {"ok": False, "error": "分析超时（60秒）"}
            code = 500
        except Exception as e:
            resp = {"ok": False, "error": str(e)}
            code = 500

        self._json(code, resp)

    def _api_status(self):
        stats_file = BASE_DIR / "wechat-stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                data = json.load(f)
            self._json(200, {"ok": True, "updated": data.get("generated_at"), "groups": len(data.get("groups", []))})
        else:
            self._json(200, {"ok": False, "error": "wechat-stats.json 不存在"})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        if "/api/" in str(args[0]):
            print(f"[api] {args[0]}")


def main():
    port = 8080
    for a in sys.argv[1:]:
        if a.startswith("--port="):
            port = int(a.split("=")[1])
        elif a.startswith("--group="):
            global GROUP_ARG
            GROUP_ARG = a.split("=", 1)[1]

    os.chdir(BASE_DIR)
    server = http.server.HTTPServer(("0.0.0.0", port), Handler)
    print(f"""
╔══════════════════════════════════════╗
║   📊 WeChat Group Stats Dashboard   ║
║   http://localhost:{port}/dashboard.html  ║
║   Ctrl+C 停止                        ║
╚══════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] 已停止")


if __name__ == "__main__":
    main()

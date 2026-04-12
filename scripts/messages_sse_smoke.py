#!/usr/bin/env python3
"""连接已启动服务上的 ``GET /api/v1/messages/stream``，打印 SSE 事件（验证推送到前端）。

前置：
  1. 本机已 ``uv run serve``（默认 http://127.0.0.1:8000）
  2. 环境变量 ``TOKEN`` 为有效 JWT（与浏览器登录后相同）

用法::

  export TOKEN='eyJ...'
  uv run python scripts/messages_sse_smoke.py

另开终端触发改密等会投递通知的操作后，本脚本应打印 ``notification`` / ``unread_count`` 行。
"""

from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzY2VhMGUzOC02MWU5LTQ1MDktYTI1MS1jN2FmNDFiNjViNmIiLCJlbWFpbCI6InN4bDUyNTM5OTlAZ21haWwuY29tIiwicm9sZXMiOlsiYWRtaW4iXSwiaWF0IjoxNzc1OTE2NzM2LCJleHAiOjE3NzY1MjE1MzZ9.zP2IOz63vrpd1E8sh5XMf7bJJ2MFHShXCPO2kULkzRA  "
    if not token:
        print("请设置环境变量 TOKEN=你的 JWT", file=sys.stderr)
        return 2
    base = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/api/v1/messages/stream"
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    print(f"GET {url}", flush=True)
    with httpx.Client(timeout=None) as client:
        with client.stream("GET", url, headers=headers) as resp:
            print("status", resp.status_code, flush=True)
            if resp.status_code != 200:
                # 流式响应不能读 .text，须先 read() 再解码
                body = resp.read()
                snippet = body.decode(errors="replace")[:800]
                print(snippet or "(empty body)", file=sys.stderr)
                return 1
            max_lines = int(os.environ.get("SSE_MAX_LINES", "30"))
            n = 0
            for line in resp.iter_lines():
                if line is None:
                    continue
                s = line.strip()
                if not s:
                    continue
                print(s, flush=True)
                n += 1
                if n >= max_lines:
                    print("-- 已达 SSE_MAX_LINES，退出 --", flush=True)
                    break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

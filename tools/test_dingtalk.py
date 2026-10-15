"""最小测试：往钉钉自定义机器人发一条文本消息，验证 webhook 是否可用。

用法：python tools/test_dingtalk.py
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def signed_url(webhook: str, secret: str) -> str:
    if not secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    payload = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    signature = urllib.parse.quote_plus(base64.b64encode(digest))
    joiner = "&" if "?" in webhook else "?"
    return f"{webhook}{joiner}timestamp={timestamp}&sign={signature}"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_env(root / ".env")

    webhook = os.environ.get("DINGTALK_WEBHOOK", "").strip()
    secret = os.environ.get("DINGTALK_SECRET", "").strip()
    if not webhook:
        print("缺少 DINGTALK_WEBHOOK，请先在 .env 里填好。")
        return 1

    body = {
        "msgtype": "text",
        "text": {"content": "【测试】早报机器人接入测试：收到这条消息，说明推送通道已经打通。"},
    }
    request = urllib.request.Request(
        signed_url(webhook, secret),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read().decode("utf-8")
            print("HTTP", response.status)
            print(text)
            data = json.loads(text)
            if data.get("errcode") == 0:
                print("成功：消息已发出，去钉钉群里看看。")
                return 0
            print("失败：钉钉返回了错误码，见上面内容。")
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"请求异常：{type(exc).__name__}: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

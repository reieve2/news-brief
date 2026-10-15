"""探测本机常见代理端口，找到能访问外网的哪一个。

用法：python tools/detect_proxy.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

PORTS = [7890, 7897, 7891, 10809, 10808, 1080, 8889, 2080, 33210, 4780]
TEST_URL = "https://www.cloudflare.com/cdn-cgi/trace"


def main() -> int:
    found = []
    for port in PORTS:
        proxy = f"http://127.0.0.1:{port}"
        try:
            response = requests.get(
                TEST_URL,
                proxies={"http": proxy, "https": proxy},
                timeout=6,
            )
            if response.status_code == 200:
                print(f"可用：{proxy}  (返回 {len(response.content)} 字节)")
                found.append(proxy)
        except Exception as exc:  # noqa: BLE001
            print(f"不可用：{proxy}  ({type(exc).__name__})")

    print()
    if found:
        print(f"建议在 config.yaml 里填：proxy: \"{found[0]}\"")
    else:
        print("没有探测到可用代理。确认代理软件正在运行，或告诉我它显示的是什么端口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""诊断单个源：打印状态码、内容类型和开头片段，用来判断源是否还有效。

用法：python tools/probe_source.py https://www.jiqizhixin.com/rss
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fetch  # noqa: E402
from common import load_config, load_env  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python tools/probe_source.py <url> [--proxy]")
        return 1

    url = sys.argv[1]
    use_proxy = "--proxy" in sys.argv

    load_env()
    cfg = load_config()
    session = fetch.make_session(cfg)

    proxies = fetch.proxies_for(cfg, use_proxy)
    try:
        response = session.get(url, proxies=proxies, timeout=20)
    except Exception as exc:  # noqa: BLE001
        print(f"请求失败：{type(exc).__name__}: {exc}")
        return 1

    print(f"状态码：{response.status_code}")
    print(f"内容类型：{response.headers.get('Content-Type', '')}")
    print(f"长度：{len(response.content)}")
    print("---- 开头 400 字节 ----")
    print(response.text[:400].replace("\n", " ")[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

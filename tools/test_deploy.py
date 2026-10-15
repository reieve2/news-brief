"""单独测试部署这一步（不重新生成早报，直接上传现有 out 目录）。

用法：python tools/test_deploy.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import load_config, load_env, setup_logging  # noqa: E402
from deploy import deploy  # noqa: E402


def main() -> int:
    load_env()
    cfg = load_config()
    log = setup_logging(cfg)
    url = deploy(cfg)
    print()
    if url:
        print(f"部署成功：{url}")
        return 0
    print("部署失败，往上翻日志看原因。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

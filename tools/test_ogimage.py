"""测试：对几条真实文章链接抓 og:image。

用法：python tools/test_ogimage.py [URL ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ogimage  # noqa: E402
from common import load_config, load_env, setup_logging  # noqa: E402
from fetch import make_session  # noqa: E402

DEFAULT_URLS = [
    "https://openai.com/index/introducing-gpt-5/",
    "https://www.ithome.com/0/795/123.htm",
    "https://huggingface.co/blog/embeddinggemma",
    "https://github.blog/news-insights/",
]


def main() -> int:
    load_env()
    cfg = load_config()
    log = setup_logging(cfg)
    session = make_session(cfg)

    urls = sys.argv[1:] or DEFAULT_URLS
    for url in urls:
        image = ogimage.fetch_image_url(cfg, session, url)
        print(f"{'✓' if image else '×'} {url}")
        if image:
            print(f"    -> {image[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

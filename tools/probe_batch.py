"""批量验证一批候选 RSS 源是否可用。

用法：python tools/probe_batch.py            # 用内置候选清单
      python tools/probe_batch.py urls.txt   # 每行一个 URL
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fetch  # noqa: E402
from common import load_config, load_env  # noqa: E402

CANDIDATES = [
    # 实验室 / 公司一手来源
    ("Google Research", "https://research.google/blog/rss/"),
    ("Apple ML Research", "https://machinelearning.apple.com/rss.xml"),
    ("AWS Machine Learning", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("Microsoft AI Blog", "https://blogs.microsoft.com/ai/feed/"),
    ("BAIR (伯克利 AI)", "https://bair.berkeley.edu/blog/feed.xml"),
    ("Stanford HAI", "https://hai.stanford.edu/news/rss.xml"),
    ("PyTorch Blog", "https://pytorch.org/blog/feed.xml"),
    ("Anthropic News", "https://www.anthropic.com/news/rss.xml"),
    # 中文科技/AI
    ("智东西", "https://zhidx.com/feed"),
    ("极客公园", "https://www.geekpark.net/rss"),
    ("界面新闻", "https://a.jiemian.com/index.php?m=article&a=rss"),
    ("36氪(备选)", "https://36kr.com/feed-newsflash"),
    # 芯片 / 算力 / 基建
    ("Data Center Dynamics", "https://www.datacenterdynamics.com/en/rss/"),
    ("EE Times", "https://www.eetimes.com/feed/"),
    ("CNBC Technology", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    # 资本 / 创业
    ("Crunchbase News", "https://news.crunchbase.com/feed/"),
    ("Sifted", "https://sifted.eu/feed"),
    # 开发者 / 开源
    ("GitHub Blog", "https://github.blog/feed/"),
    ("Lobsters", "https://lobste.rs/rss"),
    ("The New Stack", "https://thenewstack.io/feed/"),
    ("InfoQ 英文", "https://feed.infoq.com/"),
    # 快讯 newsletter
    ("TLDR AI", "https://tldr.tech/api/rss/ai"),
    ("Ben's Bites", "https://bensbites.beehiiv.com/feed"),
    ("Platformer", "https://www.platformer.news/feed"),
    # 学术补充
    ("arXiv cs.CL", "http://export.arxiv.org/api/query?search_query=cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=20"),
    ("arXiv cs.CV", "http://export.arxiv.org/api/query?search_query=cat:cs.CV&sortBy=submittedDate&sortOrder=descending&max_results=20"),
]


def verdict(body: bytes) -> str:
    head = body[:600].lower()
    if b"<rss" in head or b"<feed" in head or b"<rdf" in head:
        return "feed"
    return "不是订阅源"


def main() -> int:
    load_env()
    cfg = load_config()
    session = fetch.make_session(cfg)

    items = CANDIDATES
    if len(sys.argv) > 1:
        lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
        items = [
            (line.split("|", 1)[1].strip(), line.split("|", 1)[0].strip())
            for line in lines
            if "|" in line
        ]

    ok, bad = [], []
    for name, url in items:
        response = fetch.get(session, cfg, url, use_proxy=True, timeout=20)
        if response is None:
            bad.append((name, "请求失败"))
            print(f"× {name:<22} 请求失败")
            continue
        kind = verdict(response.content)
        if kind == "feed":
            ok.append((name, url, len(response.content)))
            print(f"√ {name:<22} {len(response.content):>8} 字节")
        else:
            bad.append((name, response.headers.get("Content-Type", "")))
            print(f"× {name:<22} {kind} ({response.headers.get('Content-Type','')})")

    print(f"\n可用 {len(ok)} / {len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""离线自检：用假数据渲染一份早报，检查排版和模板是否正常。

用法：python tools/selftest.py
生成的文件在 out/index.html，可以直接用浏览器打开看。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import load_config  # noqa: E402
from render import render_brief  # noqa: E402


FAKE_CARDS = [
    {
        "title": "示例：某公司发布新一代模型",
        "what": "这是用于检查排版的假数据，正文里故意放了一个专业术语 SOTA 和一个 MoE，用来验证点击解释是否正常工作。这一段应当控制在八十到一百二十字之间。",
        "background": "这一段说明为什么此刻发生，应当单独成一个段落。这里再出现一次 SOTA，用来确认同一个词在同一期里只标第一次。",
        "why": "这一段说明为什么重要。",
        "next": "这一段给出接下来的推测。",
        "confidence": "中",
        "importance": 4,
        "terms": [
            {
                "term": "SOTA",
                "gloss": "State of the Art，指在某个公开基准上达到当前最好成绩。不同基准之间不可直接比较。",
            }
        ],
        "sources": [{"name": "示例来源", "url": "https://example.com"}],
    },
    {
        "title": "示例：第二条，验证多卡片之间的间距",
        "what": "第二条假数据，用来确认卡片之间的间隔、编号、折叠区域都正常。这里出现 SOTA，它已经在第一条标过了，所以这次不该再有下划线。",
        "background": "背景段落，这里首次出现 MoE，应该被标上。",
        "why": "重要性段落。",
        "next": "推测段落。",
        "confidence": "高",
        "importance": 3,
        "terms": [
            {"term": "SOTA", "gloss": "这个词在第一条已经解释过，这里不应该再标。"},
            {"term": "MoE", "gloss": "混合专家模型，推理时只激活一部分参数，用更少的算力换取更大的模型容量。"},
        ],
        "sources": [
            {"name": "来源甲", "url": "https://example.com/a"},
            {"name": "来源乙", "url": "https://example.com/b"},
        ],
    },
]


def main() -> int:
    cfg = load_config()
    stats = [
        {"name": "示例源一", "count": 12, "error": ""},
        {"name": "示例源二", "count": 0, "error": "请求失败"},
    ]
    path = render_brief(
        cfg,
        FAKE_CARDS,
        "2026-01-01",
        "07:12",
        stats,
        degraded=False,
        degraded_reason="",
    )
    print(f"已生成：{path}")
    print(f"备份原文件请勿提交：{path.parent / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

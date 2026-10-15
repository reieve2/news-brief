"""部署到 Cloudflare Pages。"""

from __future__ import annotations

import logging
import re
import subprocess

from common import ROOT

logger = logging.getLogger("brief")

URL_RE = re.compile(r"https://([a-z0-9.-]+)\.pages\.dev")


def stable_url(host: str) -> str:
    """把带哈希的部署地址还原成固定地址。

    例如 76aef440.ai-daily-brief-q2d.pages.dev → ai-daily-brief-q2d.pages.dev
    """
    labels = [label for label in host.split(".") if label]
    if len(labels) >= 4:  # 最前面那段是每次部署都会变的哈希
        labels = labels[1:]
    return "https://" + ".".join(labels)


def deploy(cfg: dict) -> str | None:
    out_dir = cfg["site"].get("out_dir", "out")
    project = cfg["deploy"].get("project_name", "ai-daily-brief")
    branch = cfg["deploy"].get("branch", "main")
    command = f"npx --yes wrangler pages deploy {out_dir} --project-name {project} --branch {branch}"

    logger.info("开始部署：%s", command)
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("部署异常：%s", exc)
        return None

    output = (result.stdout or "") + (result.stderr or "")
    match = URL_RE.search(output)
    if match:
        url = stable_url(match.group(0).removeprefix("https://"))
        logger.info("部署成功：%s", url)
        return url

    logger.warning("部署未拿到网址（返回码 %s）：\n%s", result.returncode, output[-1500:])
    return None

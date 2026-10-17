# news-brief 交接文档

写给下一个会话，或者上下文被压缩后的自己。只记「不看聊天记录也能接上」的东西。

## 这是什么

每天自动产出 AI / 科技早报，外加一份周报和两条短视频素材。

- 仓库：https://github.com/reieve2/news-brief（公开，MIT）
- 本地：`D:\Desktop\2\news-brief`
- 站点：https://daily-aibrief.pages.dev
- 视频工程落在 `data/weekly/<周日日期>/video-<版本>/`，复制到 ai-media 工作区渲染

## 现在怎么跑

| 环节 | 时间 | 跑在哪 |
| --- | --- | --- |
| 早报生成 + 部署 + 钉钉推送 | 每天 07:00（北京） | GitHub Actions，cron `0 23 * * *`（UTC） |
| 兜底检查 | 每天 18:00 | 本地计划任务 `AI-Brief-Fallback` |
| 周报 + 视频工程 | 周一至周三登录后 3 分钟 | 本地启动项 `AI-Brief-Weekly.lnk` |

本地**没有**早报的登录启动项（2026-10-17 卸的，会和云端 07:00 撞车）。
`AI-Brief-Daily`（22:30）是禁用状态，不用管。`DigitalBrain-MorningBrief` 是旧项目，也已禁用。

GitHub Actions 的 schedule 不保证准时，实测有过 4 小时延迟；兜底放在 18:00 就是给这个留余量。

## 关键文件

```
config.yaml            源清单、条数、周报参数（本机路径留空，读 .env）
.env                   密钥与本机路径，不进 git
prompts/               选材、成卡、周报底稿、口播稿、分镜，全是纯文本规则
src/main.py            主流程（日报；周一还会顺手触发周报）
src/weekly.py          周报：读七天存档 → 分组底稿 → 双版口播稿 → 配音
src/tts.py             edge-tts 配音、ffmpeg 合成整轨、字幕断行
src/storyboard.py      口播稿 → 屏幕大字（含每幕对应的条目编号）
src/hyperframes.py     生成 HyperFrames 工程（分镜 + 背景 + 花字 + 字幕）
src/ogimage.py         从官方来源抓 og:image（白名单，媒体站跳过）
tools/make_video.py    组装视频工程、复制到 ai-media、调用渲染
tools/resend_brief.py  按日期补推早报，只推不生成
tools/local_fallback.py 兜底：查线上有没有今天的早报，没有才本地补
```

## 最近状态（2026-10-17）

- 今天早报没送达：云端 Secrets 缺 `DINGTALK_WEBHOOK`（静默跳过推送），本地兜底又因写日志权限被拒崩掉。两处都已修，今天的早报已补推。
- 云端 cron 从 12:00 挪到 07:00；本地兜底从 13:00 挪到 18:00；卸掉了早报的登录启动项。
- 视频：加了顶部常驻花字（`weekly.brand`）、按内容主题变化的背景光晕、官方来源素材卡片。

## 已知问题 / 待办

1. **素材图覆盖率只有 1/4 到 1/3**：只从官方来源抓（`ogimage.OFFICIAL_HOSTS`），中文媒体普遍没有 og:image。所以视频里"卡片"和"大字"两种版式交替。想提升覆盖率有两条路：加人脸检测后放宽到媒体源，或者改成用 Playwright 截一手来源页面。
2. **周报视频还没接到渲染自动化**：`make_video.py --copy --render` 已能跑通，但周报流程本身不自动调它。
3. **抖音视频抓取**：`ai-media\tools\douyin_grab.py` 可用（浏览器内取直链），但抓到的只有画面轨，音频轨要另外处理。
4. 兜底脚本 2026-10-17 的 `PermissionError` 根因未定位（文件当时被占用，可能和 `aiworker` 账号有关），目前只加了容错。

## 踩过的坑（别重犯）

- `.bat` / `.vbs` 必须 CRLF，`.ps1` 含中文字符串必须带 UTF-8 BOM，否则 PowerShell 5.1 按 GBK 解码会解析失败。
- `.cue` 用 `left:50%` 定位会让可用宽度只剩半个屏幕，字幕被迫折行；要用 `left:0; right:0; margin:auto`。
- 字数约束必须**由代码算好**告诉模型，让它自己做「总字数 ÷ 段数」它不执行。
- 喂给口播稿的素材只给要点；给全文它就照着全文长度写。
- `Path("")` 会变成当前目录 `.`，判空之后再 `Path()`。
- 媒体站的 og:image 可能是人物照（TechCrunch 实测），所以只认官方来源白名单。

## 新对话怎么开始

> 读 `D:\Desktop\2\news-brief\HANDOFF.md` 和 `README.md`，继续 news-brief 的工作。

有具体任务就直接说任务，我会按 AGENTS.md 的流程先 grill 再动手。

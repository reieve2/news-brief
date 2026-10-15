# 每日 AI 科技早报

每天自动抓取全球 AI / 科技资讯，用 DeepSeek 挑出 5–8 条最值得知道的事，写成深度卡片，  
渲染成手机网页并推送到钉钉。

## 一次性准备

1. 安装依赖
   ```
   pip install -r requirements.txt
   ```
2. 填 `.env`
   ```
   DINGTALK_WEBHOOK=...   # 已填好
   DINGTALK_SECRET=       # 机器人安全设置选了「加签」才需要填
   DEEPSEEK_API_KEY=...   # 去 platform.deepseek.com 拿
   ```
3. 改 `config.yaml`
   - `network.proxy`：填你的代理地址，例如 `http://127.0.0.1:7890`。  
     标记 `proxy: true` 的源会走它，中文源直连不消耗代理流量。
   - `site.base_url`：第一次部署成功后程序会自动回填，不用手动改。
   - `sources`：增删源就在这里，`weight` 越高质量越被看重。
4. 部署授权（只在第一次需要）
   ```
   npx wrangler login
   ```
   浏览器里授权一次。**但自动运行的任务没有交互窗口，wrangler 用不了这种方式**，  
   所以还要建一个 API token：
   1. 打开 <https://dash.cloudflare.com/profile/api-tokens>
   2. Create Token → Custom token
   3. Permissions 选 `Account` → `Cloudflare Pages` → `Edit`
   4. Account Resources 选你自己的账号，创建后复制
   5. 把它填进 `.env` 的 `CLOUDFLARE_API_TOKEN`

## 日常使用

手动跑一次完整流程：

```
python src/main.py
```

常用参数：

| 参数                            | 作用               |
| ----------------------------- | ---------------- |
| `--dry-run`                   | 只在本地生成网页，不部署、不推送 |
| `--force`                     | 忽略「今天已生成过」，强制重跑  |
| `--limit 3`                   | 只出 3 条，调试用       |
| `--only-sources 机器之心,量子位`     | 只用名字匹配的源，调试用     |
| `--no-deploy` / `--no-notify` | 跳过部署 / 跳过推送      |

第一次建议这样试：

```
python src/main.py --dry-run --limit 2 --only-sources 雷峰网,IT之家
```

然后打开 `out/index.html` 看排版。

## 定时

已经装好两处触发，都指向 `run_daily.bat`（通过 `run_hidden.vbs` 静默运行，不弹黑窗）：

1. **登录后 2 分钟**（主力）：`startup_brief.vbs` 放在「启动」文件夹里。  
   开机触发在 Windows 上需要管理员权限，放启动文件夹不需要，效果一样。
2. **每晚 22:30**（兜底）：计划任务 `AI-Brief-Daily`。

重新安装：`powershell -ExecutionPolicy Bypass -File tools\install_tasks.ps1`

两次都跑没坏处：同一天已经成功生成过，程序会自动跳过（除非加 `--force`）。  
日志在 `logs/` 下按日期存放，`logs/scheduler.log` 记录每次调度的起止和返回码。

注意：`.bat` 和 `.vbs` 必须是 **CRLF 换行**，改成 LF 会让 cmd 把每行开头吃掉。  
改动这两个文件后跑一下 `tools/fix_line_endings.ps1`。

## 目录

```
config.yaml          配置：源清单、代理、条数、时间窗
.env                 密钥（不进 git）
prompts/             选材与成卡的两个 prompt，可以直接改
src/                 程序
data/briefs/         每天早报的 JSON 存档
out/                 生成的网页（部署的就是这个目录）
logs/                运行日志
```

## 小工具

```
python tools/show_brief.py             在命令行里看最新一期早报
python tools/show_brief.py 2026-10-07  看指定日期
python tools/test_fetch.py             只测抓取，不花 token
python tools/probe_source.py <url>     看某个源到底返回了什么
python tools/probe_batch.py            批量验证一批候选源
python tools/detect_proxy.py           探测本机代理端口
python tools/selftest.py               用假数据渲染网页，检查排版
python tools/test_deploy.py            单独测部署
python tools/test_dingtalk.py          验证钉钉通道
```

## 术语点击解释

卡片里的技术术语带虚线，点一下从屏幕底部滑出解释。解释是生成早报时一起写好的，  
藏在网页里，点击瞬间展开，不需要联网、不依赖电脑开机。

规则写在 `prompts/compose.md` 的 terms 部分：只标技术术语（不标公司名、人名、产品名、  
模型名），每张卡片最多 2 个，同一个词在一期里只标第一次出现的地方。

觉得标多了或标少了，改那个 prompt 里的规则就行；`src/compose.py` 里的 `TERM_LIMIT`  
是硬上限。模型给出的术语如果没在正文里原样出现，会被自动丢弃（`clean_terms`）。

## 出问题先看这几个地方

- **钉钉收不到**：先跑 `python tools/test_dingtalk.py`，看返回的 errcode。
- **某几个源老是空的**：看 `logs/` 里对应的报错，多半是这个源改版或下线了，  
  在 `config.yaml` 里换掉或删掉即可。
- **网页没更新**：看 `data/state.json` 里的 `last_date`，判断是不是被「当天已生成」拦下了，  
  加 `--force` 重跑。
- **代理没开**：外文源会全部失败，早报会退化成只有中文源，钉钉里会标注「降级版本」。

## 许可

MIT License，见 [LICENSE](LICENSE)。署名用了 GitHub 账号名（`reieve2`），要改成你的名字或组织名，直接改 LICENSE 第一行即可。

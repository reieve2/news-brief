# 每日 AI 早报

每天中午，把全网 50 多个信息源（Hacker News、TechCrunch、量子位、IT之家、少数派、arXiv……）
里的 AI 与科技动态，自动筛成 5-7 张卡片。每条讲清「是什么 · 背景 · 为什么重要 · 接下来」，
正文里带虚线的术语点一下就有解释。

**在线读**：<https://ai-daily-brief-q2d.pages.dev>　**往期**：页面底部　**订阅**：见下

---

# 一、我只想每天看到早报（不用装任何东西）

**第一步**：手机浏览器打开 <https://ai-daily-brief-q2d.pages.dev>，然后「分享 → 添加到主屏幕」。
以后点一下图标就能看，和 App 一样。

**第二步（可选，但推荐）**：用 RSS 订阅，让它每天自动送到你面前。

> **RSS 是什么？** 一种很老但完全免费、没有广告的订阅方式。你把一个网址交给阅读器，
> 它就把新内容自动收进来。不用注册账号、不用给手机号、没有算法推荐，也不会漏掉某一期。

怎么订：

1. 复制这个网址：`https://ai-daily-brief-q2d.pages.dev/feed.xml`
2. 装一个阅读器，把网址粘进去：
   - iPhone：NetNewsWire（免费）或 Reeder
   - 安卓：Feedly、Inoreader
   - 电脑：浏览器扩展 Feedbro，或邮件客户端 Thunderbird
3. 完成。以后每期自动出现，不用你记着来刷。

就这些。不需要注册、不需要安装、不需要懂技术。

---

# 二、我想自己搭一套

## 先看清楚你要付出什么

| 你要有 | 说明 |
| --- | --- |
| 一个 GitHub 账号 | 免费注册。托管版靠它的免费服务器定时跑 |
| 一个 DeepSeek 账号 | 注册免费，负责筛选和写卡片。按量付费，日常用一天几分钱到几毛钱 |
| 一个 Cloudflare 账号 | 免费注册，用来放网页 |
| 一点点耐心 | 下面每一步都是点按钮或复制粘贴，不需要懂编程 |

不需要买服务器、不需要买域名、不需要显卡，也不需要电脑常开。

## 路线 A：托管版（推荐，电脑不用常开）

整套跑在 GitHub 的免费服务器上，每天中午自动抓取、生成、部署。配置一次，之后不用管。

### 第 1 步 · 把仓库复制到你自己的账号

点本页面右上角的 **Fork**，等几秒。这样你就有了一个属于自己的副本，之后所有改动都在你的副本里。

### 第 2 步 · 改一个名字，避免撞车

在你 fork 出来的仓库里，打开 `config.yaml`，把这两行改成你自己的：

```yaml
deploy:
  project_name: ai-daily-brief     # 改成 my-ai-brief-加上你的名字，比如 my-ai-brief-tom
```

> 为什么：Cloudflare 的项目名全球唯一，不改的话会和别人的撞车，部署会失败。

### 第 3 步 · 准备两个密钥

**（a）DeepSeek 的 key** —— 去 <https://platform.deepseek.com> 注册登录，
左侧菜单找 **API keys** → 创建 → 复制那串 `sk-` 开头的字符。

**（b）Cloudflare 的 token** —— 去 <https://dash.cloudflare.com> 注册（免费），然后：

1. 打开 <https://dash.cloudflare.com/profile/api-tokens>
2. **Create Token** → **Custom token**
3. Permissions 选 `Account` → `Cloudflare Pages` → `Edit`
4. Account Resources 选你自己的账号，创建后复制那串 token

### 第 4 步 · 把密钥存进仓库

在你 fork 的仓库里：**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

依次添加三条（名字必须一模一样）：

| Name | Secret |
| --- | --- |
| `DEEPSEEK_API_KEY` | 第 3 步 (a) 复制的 key |
| `CLOUDFLARE_API_TOKEN` | 第 3 步 (b) 复制的 token |
| `CLOUDFLARE_ACCOUNT_ID` | 你的 Cloudflare 账户 ID（见下） |

> **账户 ID 在哪找**：登录 <https://dash.cloudflare.com>，在任意域名的「概述」页右侧，
> 或右上角头像 → Account ID，是一串 32 位字符（形如 `88802e9e4f55245f2ba3885bcbe9658f`）。
> 这一条不能漏——只在本地跑时 wrangler 能自己找到账号，但在云端必须显式告诉它。

> 想顺便把早报推到钉钉，再加 `DINGTALK_WEBHOOK`（机器人地址）和 `DINGTALK_SECRET`（选了「加签」才需要）。不用钉钉就跳过。

### 第 5 步 · 跑一次试试

仓库页面点 **Actions** → 左侧选「每日早报」→ 右侧 **Run workflow** → 绿色按钮。

大约 2-3 分钟。跑完后：

- Actions 的日志末尾会出现一个 `https://xxxx.pages.dev` 地址，**那就是你的早报站**；
- 仓库的 `data/briefs/` 目录里会多出一个当天日期的 JSON，这就是归档。

### 第 6 步 · 以后不用管了

每天北京时间中午 12 点自动跑一次。想改时间，编辑 `.github/workflows/daily-brief.yml` 里的：

```yaml
- cron: "0 4 * * *"     # GitHub 用 UTC，北京时间 = UTC + 8，所以 04:00 = 12:00
```

## 路线 B：本地版（装在自己电脑上）

适合想改代码、或者不想把 key 交给 GitHub 的人。

### 步骤 1 · 装 Python

去 <https://www.python.org/downloads/> 下载安装。

> ⚠️ 安装界面第一屏有个复选框 **Add Python to PATH**，一定要勾上。
> 忘了勾，后面所有命令都会报「找不到 python」，这是新手最常踩的坑。

### 步骤 2 · 下载项目并装依赖

```
git clone https://github.com/reieve2/news-brief
cd news-brief
pip install -r requirements.txt
```

（没装过 git 的话，在 GitHub 页面点绿色 **Code** → **Download ZIP**，解压后进入文件夹执行第二行。）

### 步骤 3 · 填两样东西

**① DeepSeek 的 key（必须）** —— 在项目根目录新建一个文本文件，命名 `.env`（注意开头有个点），内容：

```
DEEPSEEK_API_KEY=粘贴你复制的 key
DINGTALK_WEBHOOK=
DINGTALK_SECRET=
```

**② 代理（可选，但在国内很关键）** —— 打开 `config.yaml`，找到 `network.proxy`，填你能用的代理地址（例如 `http://127.0.0.1:7890`）。

> 不填也能跑，但**国外的源会全部抓不到**，早报会退化成只有中文源——那一期网页上会明确标注「降级版本」。

### 步骤 4 · 先试跑一次

```
python src/main.py --dry-run --limit 2 --only-sources 雷峰网,IT之家
```

`--dry-run` 的意思是「只在本地生成网页，不推送、不上传」。跑完打开 `out/index.html` 看排版，
满意了再去掉参数跑完整版：

```
python src/main.py
```

### 步骤 5 · 设成每天自动跑

- **Windows**：`powershell -ExecutionPolicy Bypass -File tools\install_tasks.ps1`
- **Mac / Linux**：把 `python src/main.py` 加进 crontab（`crontab -e`）

---

# 三、常见问题

**Q：DeepSeek 的 key 会被盗用吗？**
A：托管版存在 GitHub 的 Secrets 里（只有 Actions 运行时能读到，别人看不到）；
本地版只存在你自己电脑的 `.env` 文件里（这个文件默认不进 git）。两种都不会被上传到别处。

**Q：一共要花多少钱？**
A：GitHub Actions 和 Cloudflare Pages 都在免费额度内（公开仓库的 Actions 完全免费）。
唯一的开销是 DeepSeek 的模型调用，按量付费，一天几分钱到几毛钱。

**Q：跑不起来怎么办？**
A：按顺序查三样 ——
① 报「找不到 python」：装 Python 时没勾 Add Python to PATH，重装一次；
② 报网络错误：本地版多半是代理没开或没填对；
③ 报权限错误：检查 `.env` 文件名是不是被系统改成了 `.env.txt`。

**Q：能改成别的领域吗（比如财经、医药）？**
A：能。`config.yaml` 的 `sources` 就是源清单，换成你要的源；选材和成卡的规则在 `prompts/` 目录，直接改里面的文字。

**Q：为什么是中文？能出英文版吗？**
A：`config.yaml` 里 `brief.language` 改成 `en` 即可。

**Q：托管版和本地版能同时跑吗？**
A：可以但不建议——同一天会重复调用模型、重复部署。挑一条就好。

---

# 技术细节

以下是给想改代码的人看的，只想用的话上面就够了。

## 一次性准备

1. 安装依赖
   ```
   pip install -r requirements.txt
   ```
2. 填 `.env`（见上文）
3. 改 `config.yaml`
   - `network.proxy`：填你的代理地址，例如 `http://127.0.0.1:7890`。
     标记 `proxy: true` 的源会走它，中文源直连不消耗代理流量。
   - `site.base_url`：第一次部署成功后程序会自动回填，不用手动改。
   - `sources`：增删源就在这里，`weight` 越高质量越被看重。
4. 部署授权（本地版第一次需要）
   ```
   npx wrangler login
   ```
   浏览器里授权一次。**但自动运行的任务没有交互窗口，wrangler 用不了这种方式**，
   所以还要建一个 API token（步骤同路线 A 第 3 步 (b)），填进 `.env` 的 `CLOUDFLARE_API_TOKEN`。

## 日常使用

```
python src/main.py
```

常用参数：

| 参数 | 作用 |
| --- | --- |
| `--dry-run` | 只在本地生成网页，不部署、不推送 |
| `--force` | 忽略「今天已生成过」，强制重跑 |
| `--limit 3` | 只出 3 条，调试用 |
| `--only-sources 雷峰网,IT之家` | 只用名字匹配的源，调试用 |
| `--no-deploy` / `--no-notify` | 跳过部署 / 跳过推送 |

## 定时（本地版）

已经装好两处触发，都指向 `run_daily.bat`（通过 `run_hidden.vbs` 静默运行，不弹黑窗）：

1. **登录后 2 分钟**（主力）：`startup_brief.vbs` 放在「启动」文件夹里。
2. **每晚 22:30**（兜底）：计划任务 `AI-Brief-Daily`。

重新安装：`powershell -ExecutionPolicy Bypass -File tools\install_tasks.ps1`

同一天已经成功生成过，程序会自动跳过（除非加 `--force`）。
日志在 `logs/` 下按日期存放，`logs/scheduler.log` 记录每次调度的起止和返回码。

注意：`.bat` 和 `.vbs` 必须是 **CRLF 换行**，改成 LF 会让 cmd 把每行开头吃掉。
改动这两个文件后跑一下 `tools/fix_line_endings.ps1`。

## 云端 + 本地兜底（推荐的稳妥组合）

只用云端已经够用；如果担心哪天云端没跑成导致断更，可以再挂一个本地兜底检查：

```
python tools/local_fallback.py           # 检查线上有没有今天的早报，没有才本地补一次
python tools/local_fallback.py --check   # 只检查、不补跑
```

它的判断逻辑是「线上今天有没有」，所以云端正常时它什么都不做，只在云端漏了的时候补位——
不会出现两边各跑各的、重复抓取重复花钱。配一个每天固定时间的计划任务即可
（本机用的是每天 13:00，并勾选「错过则在开机后补跑」）。

## 目录

```
config.yaml          配置：源清单、代理、条数、时间窗
.env                 密钥（不进 git）
.github/workflows/   托管版的定时任务
prompts/             选材与成卡的两个 prompt，可以直接改
src/                 程序
data/briefs/         每天早报的 JSON 存档
out/                 生成的网页（部署的就是这个目录，不进 git）
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
python tools/show_weekly.py            看最新一期周报的底稿和口播稿
```

## 术语点击解释

卡片里的技术术语带虚线，点一下从屏幕底部滑出解释。解释是生成早报时一起写好的，
藏在网页里，点击瞬间展开，不需要联网、不依赖电脑开机。

规则写在 `prompts/compose.md` 的 terms 部分：只标技术术语（不标公司名、人名、产品名、
模型名），每张卡片最多 2 个，同一个词在一期里只标第一次出现的地方。

觉得标多了或标少了，改那个 prompt 里的规则；`src/compose.py` 里的 `TERM_LIMIT`
是硬上限。模型给出的术语如果没在正文里原样出现，会被自动丢弃（`clean_terms`）。

## 一周汇总（周报）

每周一日报跑完后自动检查一次：如果上一个完整自然周（周一到周日）还没做过周报，就接着做。

数据来自 `data/briefs/` 里这七天的存档，**不重新抓取**。流程是：跨天合并同一件事 →
按可信度（排除「低」）和影响力挑出 10–12 条 → 按主题分 3–5 组、每组写两句归纳 →
出底稿网页和两份口播稿 → 配音。

两份口播稿：

- **抖音版**：60 秒左右，讲 3 条，3 秒钩子 + 短句。
- **B站版**：180 秒左右，讲 9 条，每条带「为什么重要」。

配音用 edge-tts，音色、语速、段落间隔在 `config.yaml` 的 `weekly.versions` 里。
产物落在 `data/weekly/<周日日期>/`：

```
digest.json           底稿（分组 + 条目）
script-douyin.json    抖音口播稿
script-bili.json      B站口播稿
assets-douyin/        分段 mp3 + voice_timeline.json + cues.json
assets-bili/
summary.json          这一期的统计
```

`assets-*` 的目录写法和 `O:\ai-media` 里现有项目的约定一致，复制进对应项目就能渲染，
**news-brief 本身不写那个目录**。

手动跑：

```
python src/main.py --weekly-only                                   # 只做周报
python src/main.py --weekly-only --week-end 2026-10-16 --force     # 指定覆盖到哪天，测试用
python src/main.py --weekly-only --no-audio                        # 只出文本不配音
python src/main.py --weekly                                        # 日报 + 强制做周报
```

规则在 `prompts/weekly_digest.md`（选材与分组）和 `prompts/weekly_script.md`（口播风格），
直接改文字即可。`config.yaml` 的 `weekly.digest_limit` 是底稿条数硬上限。

两个已经踩过的坑，改 prompt 时注意：**字数约束必须由代码算好告诉模型**，
让它自己做「总字数 ÷ 段数」它不会执行（实测 1883 字对 900 字预算，三次重写纹丝不动）；
**喂给口播稿的素材要只给要点**，给全文它就照着全文的长度写。

## 出问题先看这几个地方

- **钉钉收不到**：先跑 `python tools/test_dingtalk.py`，看返回的 errcode。
- **某几个源老是空的**：看 `logs/` 里对应的报错，多半是这个源改版或下线了，
  在 `config.yaml` 里换掉或删掉即可。
- **网页没更新**：看 `data/state.json` 里的 `last_date`，判断是不是被「当天已生成」拦下了，
  加 `--force` 重跑。
- **代理没开**：外文源会全部失败，早报会退化成只有中文源，网页上会标注「降级版本」。
- **托管版失败**：仓库的 Actions 页面能看到完整日志；常见原因是 Secrets 名字打错，或 `deploy.project_name` 和别人撞车。

## 许可

MIT License，见 [LICENSE](LICENSE)。署名用了 GitHub 账号名（`reieve2`），要改成你的名字或组织名，直接改 LICENSE 第一行即可。

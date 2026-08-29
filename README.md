# x-bookmarks-short-video-lookup

> 你收藏了一堆 X 推文，想找里面带短视频（≤10 分钟）的，但几百条翻起来太累？
> 这个 skill 扫描你知识库里的每日 X bookmarks 原文，自动批量查出每条视频的时长，30 秒给你一张「哪些是短视频」的清单。
>
> Scan your daily X bookmarks archive and list every bookmarked tweet that contains a short video (≤10 min), with exact durations.

**[中文](#中文) | [English](#english)**

---

<a name="中文"></a>
## 中文

### 这能解决什么问题

你的 X 收藏里散落着大量视频推文：AI 工具演示、时事评论、口播素材……但你不知道哪条是短视频、哪条是长节目。人工逐条点开看？太慢。这个 skill 用 `bird` CLI 批量读取每条推文的真实媒体时长（`durationMs`），一次性把短视频筛出来。

**用了之后**：一条命令，90 秒，输出按时长排序的短视频清单（含推文链接、收藏日期、时长），并区分「推文自带视频」和「引用他人视频」，自动去重（同一视频被多天批次重复收藏只算一次）。

### 安装

```bash
npx skills add cogitate3/x-bookmarks-short-video-lookup --skill x-bookmarks-short-video-lookup
```

### 使用

```bash
python3 ~/.hermes/skills/social-media/x-bookmarks-short-video-lookup/scripts/lookup_x_bookmark_videos.py --minutes 10
```

- 默认扫描 `/root/obsidianHermes/01_raw/notes/x-bookmarks/`（smaug-bookmarks-obsidian-ingest 管线产物）
- 其他知识库路径：`--bookmarks-dir /path/to/vault/01_raw/notes/x-bookmarks`
- 自定义阈值：`--minutes 5`（找 5 分钟以内的）

输出四类清单：**短视频（≤N 分钟）** / **长视频** / **已删除** / **外部视频链接**（YouTube 等，单独列出）。

### 自然语言触发示例

- 「找收藏的 X 里的短视频」
- 「哪些收藏推文带视频，10 分钟以内的」
- 「帮我看看知识库里每日 bookmarks 的视频推文」

### 前置条件

- [ ] `bird` CLI：`npm install -g bird-cli`（或按 `references/porting.md` 安装），配置 X 登录 cookie（`--auth-token` + `--ct0` 或浏览器 profile）
- [ ] Python 3.8+（脚本纯标准库，无第三方依赖）
- [ ] 知识库里有每日 X bookmarks 批次文件（smaug-bookmarks-obsidian-ingest 或同类管线的产物：`*-smaug-bookmarks-batch-prepared.json`）

### 工作原理

1. 扫描所有 `*-smaug-bookmarks-batch-prepared.json`，在 `bookmarks[].links[]` 里找 `/video/` 链接（X 原生视频）和 `type=video` 链接（外部视频）
2. 用 `bird read <id> --json` 逐条取 `media[].durationMs`（真实时长）
3. 按阈值过滤 + 按视频推文 id 去重，输出报告

> 为什么不用官方 API？prepared JSON 的 `media` 字段恒为空，时长必须逐条调接口。`xurl`（官方 API）未注册 app 会 401，`bird`（X 内部 GraphQL 接口）是本方案实测唯一可靠取时长的途径。

### Troubleshooting

| 问题 | 解决 |
|------|------|
| `找不到 bird CLI` | 按 `references/porting.md` 装 bird + 认证：`bird read <任意推文id> --json` 能返回 `durationMs` 才算成功 |
| `找不到 bookmarks 数据目录` | 你的 vault 路径不同，用 `--bookmarks-dir /path/to/vault/01_raw/notes/x-bookmarks` 显式指定 |
| 某条推文显示「已删除」 | 推文已被作者删除或设私密，`bird` 返回空——这是预期行为，不重试 |
| 结果里外部视频链接是 YouTube 频道页 | 频道链接（`@channel`）不是单条视频，脚本单独列出，需要手动判断 |
| YouTube 视频查不到时长 | yt-dlp / innertube API 都被反爬拦截，用 oEmbed 拿标题 + web_extract 抓章节判断（详见 `references/core-workflow.md`） |

### 风险与限制

- **账号相关**：bird 走 X 登录态（GraphQL），高频调用有触发风控的风险（脚本默认 0.8s/条间隔，62 条约 90 秒，风险可控）
- **只读操作**：本 skill 只读取推文媒体信息，不发帖、不改收藏
- 外部视频链接（YouTube/B站）时长需单独验证，脚本不自动判断

### 致谢

- [bird](https://x.com/xdevplatform) — X 内部 GraphQL CLI（v0.8.0），负责读取推文媒体时长
- smaug-bookmarks-obsidian-ingest — 知识库每日 X bookmarks 摄入管线，本 skill 的数据源
- [yao-meta-skill](https://github.com/yaojingang/yao-meta-skill) — skill 治理评估（90 分 governed 档）

### License

MIT

---

<a name="english"></a>
## English

### What it does

You've bookmarked hundreds of X posts. Which ones contain short videos (≤10 min)? This skill scans your daily X bookmarks archive, batch-fetches real media durations via the `bird` CLI, and outputs a deduplicated short-video list with exact timings, links, and bookmark dates.

### Install

```bash
npx skills add cogitate3/x-bookmarks-short-video-lookup --skill x-bookmarks-short-video-lookup
```

### Usage

```bash
python3 ~/.hermes/skills/social-media/x-bookmarks-short-video-lookup/scripts/lookup_x_bookmark_videos.py --minutes 10
```

Scans `/root/obsidianHermes/01_raw/notes/x-bookmarks/` by default; override with `--bookmarks-dir`. Outputs four categories: **short videos (≤N min)** / **long videos** / **deleted** / **external video links**.

### Prerequisites

- [ ] `bird` CLI (`npm install -g bird-cli`) with X login cookies configured
- [ ] Python 3.8+ (stdlib only)
- [ ] Daily X bookmarks batch files in your vault (`*-smaug-bookmarks-batch-prepared.json`)

### How it works

1. Scan all batch JSONs for `/video/` links (native X video) and `type=video` links (external)
2. Fetch real durations via `bird read <id> --json` → `media[].durationMs`
3. Filter by threshold + dedupe by video tweet id

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `bird CLI not found` | Install bird + configure X cookies (see `references/porting.md`) |
| `bookmarks dir not found` | Use `--bookmarks-dir /path/to/vault/01_raw/notes/x-bookmarks` |
| Tweet shows "deleted" | Author removed it — expected, don't retry |
| YouTube duration unknown | yt-dlp/innertube are bot-blocked; use oEmbed + web_extract chapters |

### License

MIT

# X 收藏短视频查找 — 核心工作流

> 本文件是 `x-bookmarks-short-video-lookup` 的主干。SKILL.md 只是入口；
> 每次运行按 SKILL.md 的「加载协议」读完本文件再动手。

## 为什么存在

prepared JSON 的 `media` 字段**恒为空**——时长信息在 JSON 里根本不存在，
必须逐条调 X 接口取。`xurl`（官方 API）未注册 app 会 401；**`bird` CLI 可用**
（`bird read <id> --json` 返回 `media[].durationMs`），是本方案唯一可靠取时长的途径。

## 数据源与信号

| 数据源 | 路径 | 视频信号 |
|---|---|---|
| 每日批次 JSON | `<vault>/01_raw/notes/x-bookmarks/*-smaug-bookmarks-batch-prepared.json` | `bookmarks[].links[]` 里 `type=media` 且 URL 含 `/video/1` → X 原生视频；`type=video` → 外部视频（YouTube 等） |
| 每日批次原文 | `同目录 *-smaug-bookmarks-batch.md` | Links 段含 `/video/` 链接（与 JSON 一致，可交叉验证） |
| 全量快照 | `2026-04-16-x-bookmarks-all-raw.json` | 有 `durationMs` 但只覆盖 4-16 前收藏，与每日批次（4-18 起）**无交集**，不可用 |

`<vault>` 默认 `/root/obsidianHermes`，可用 `--bookmarks-dir` 覆盖。

**关键坑**：link 的 URL 字段名可能是 `url` 或 `expanded` 或 `original`，
必须三选一兜底：`link.get('url') or link.get('expanded') or link.get('original')`。
`type=media` 的链接里也有大量 `/photo/1`（图片），只有 `/video/` 才是视频。

**⚠️ 2026-07-01 起管线分类变化（重要）**：4-18~6-30 的视频链接标 `type=media` + `/video/1`；
7-01 之后**同类链接改标 `type=tweet`**（`media` 类型基本消失）。因此扫描时
**`tweet` 类型链接必须也纳入候选**，交给 bird 验证是否带视频——否则 7 月后的视频全部漏掉
（2026-08-28 全量实测：7-01 以来 183 条 tweet 链接中 33 条带视频、32 条 ≤10min）。

**根因（2026-08-28 已查实）**：不是 smaug 代码变了，是 **X 平台侧 t.co 短链重定向行为在
7-01 前后变化**。smaug 的 `expandTcoLink()`（processor.js 第 426 行）用 HTTP HEAD 跟随
重定向取最终 URL，分类逻辑（第 716-720 行）看 URL 是否含 `/video/`：
- 7-01 前：视频短链 HEAD 展开 → `https://x.com/.../status/xxx/video/1`（带 /video/）→ 标 `media`
- 7-01 后：同一短链 HEAD 展开 → `https://x.com/.../status/xxx`（不带 /video/）→ 标 `tweet`
本地 smaug-tool（`/root/.hermes/hermes-agent/smaug-tool/`）代码与 config 自 8-13 部署以来未变。
修复方向：smaug 分类逻辑改为「tweet 链接也尝试 fetchTweet 取 media」，或查找时含 tweet 候选（本 skill 已实现）。

## 推荐执行方式（最快）

```bash
python3 <skill_dir>/scripts/lookup_x_bookmark_videos.py --minutes 10
```

一键完成：扫描 JSON → bird 批量取时长 → 输出短视频/长视频/已删/外部链接四类清单。
62 个唯一视频约 90 秒跑完。全量 JSON 结果落 `/tmp/x_bookmark_videos.json`。

## 手动流程（不用脚本时）

### 1. 扫描所有批次 JSON，提取视频信号

```python
import json, glob, re
video_bms = {}
for f in sorted(glob.glob('/root/obsidianHermes/01_raw/notes/x-bookmarks/*-smaug-bookmarks-batch-prepared.json')):
    date = f.split('-smaug')[0]
    with open(f) as fh: data = json.load(fh)
    for bm in data.get('bookmarks', []):
        vid_urls, ext_urls = set(), set()
        for link in (bm.get('links') or []):
            if not isinstance(link, dict): continue
            ltype = link.get('type','')
            url = (link.get('url') or link.get('expanded') or link.get('original') or '')
            if '/video/' in url: vid_urls.add(url)
            elif ltype == 'video' and url: ext_urls.add(url)
        if vid_urls or ext_urls:
            key = (date, bm.get('author'), bm.get('id'))
            video_bms.setdefault(key, {'vid':set(), 'ext':set()})
            video_bms[key]['vid'] |= vid_urls
            video_bms[key]['ext'] |= ext_urls
```

- 从 `/video/` URL 用正则 `r'/status/(\d+)/video'` 提取视频所在推文 id
- 区分「自带视频」（`vid_id == bm_id`）与「引用他人视频」（`vid_id != bm_id`）
- 同一推文被多天批次重复收藏很常见（如 5-19~5-22 连抓），**按视频推文 id 去重**后再报数

### 2. 用 bird 批量取时长（核心步骤）

```bash
bird read <tweet_id> --json
# 返回 {"media":[{"type":"video","durationMs":49792,...}]}
```

批量脚本要点（287 条约 6 分钟跑完）：
- `subprocess.run([bird,'read',tid,'--json'], capture_output=True, text=True, timeout=40)`
- 每条之间 `time.sleep(0.8)` 防限流
- **X 批量限流（2026-08-28 实测）**：287 条连续查询时后半段全挂（返回空）——
  必须带重试（单条 2 次）+ 连续 15 条失败判定限流自动降速 3 倍
- 解析 `json.loads(out)` → `media[0].durationMs`（毫秒）
- 失败处理：`empty` 输出 = 推文已删（记录为「已删/无法读取」，不要反复重试）
- **环境坑**：bird 需要 X 登录 cookie（TWITTER_AUTH_TOKEN/CT0 环境变量或浏览器 profile）。
  execute_code 工具环境**没有**这些变量（terminal 有）——批量查询必须在 terminal 环境跑，
  否则全部返回「No Twitter cookies found」→ 结果全 none（不是推文删了！）

### 3. 过滤短视频

- `durationMs <= 600000` → 短视频（≤10 分钟）
- 输出格式：`{date} [{自|引}] @{author} {m}m{s:02d}s | https://x.com/{author}/status/{bm_id}`

### 4. 外部视频链接（YouTube/B站）单独处理

- YouTube **频道链接**（`@channel`）不是单条视频，不算
- 具体视频 `watch?v=`：`curl -s "https://www.youtube.com/oembed?url=...&format=json"` 拿标题；
  时长用 web_extract 抓页面章节（`00:00` 到最后章节即时长下限）判断
- **yt-dlp 会被 YouTube 反爬拦截**（`Sign in to confirm you're not a bot`），不要浪费时间
- innertube API 也被拦；B站 412 风控页面（bilibili 链接抓取返回验证码页）

### 5. 汇总报告

- 短视频清单（按日期排序，标 自带/引用）+ 去重说明
- 排除项：长视频（>10min）、已删推文、外部长节目
- 报告给用户前**先确认是否要落盘知识库**（07_outputs/ 或 06_resources/Twitter/），不主动写

## Pitfalls（踩过的坑）

1. **prepared JSON `media` 恒为空**——别搜 `media` 字段，搜 `links` 里的 `/video/`
2. **xurl 未注册 app 会 401**（`No apps registered`）——直接走 bird
3. **link URL 字段名三选一**：`url`/`expanded`/`original`
4. **`type=media` 混有图片**——只有 `/video/` 才是视频
5. **重复收藏去重**：同视频推文被多天批次重复抓取（5-19~5-22 尤其严重），按视频 id 去重
6. **bird 读已删推文**返回空 → 标「已删」，不重试
7. **YouTube 反爬**：yt-dlp/innertube/curl 都拦，用 oEmbed（标题）+ web_extract（章节时长）
8. 全文快照 JSON（4-16）有 durationMs 但覆盖不到每日批次——别混用

## Verification（验收）

- 短视频 + 长视频 + 已删 + 外部链接四类都有明确输出，无遗漏
- 时长单位毫秒（durationMs），换算分钟时 `//60000` 取整
- 报告含去重计数（唯一视频数 vs 原始记录数）

## 历史结果参考

- 2026-08-28 首次执行（仅 media 扫描）：116 条视频记录 → 62 唯一视频 → 55 短视频 + 6 长 + 1 已删 + 20 外部链接
- 2026-08-28 诊断发现（管线分类变化）：7-01 起视频链接改标 `type=tweet`，老扫描漏掉 7 月后全部视频。
  全量验证 183 条 tweet 链接 → 33 条带视频（32 条 ≤10min）。合并后完整结果：**87 短视频 + 7 长视频**

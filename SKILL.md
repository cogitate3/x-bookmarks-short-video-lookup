---
name: x-bookmarks-short-video-lookup
description: 找收藏的 X 推文中的短视频（≤10分钟）时使用，bird 取时长输出清单。
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [x, twitter, bookmarks, video, short-video, obsidian, bird]
    related_skills: [xurl, x-video-collect, smaug-bookmarks-obsidian-ingest]
---

# X 收藏短视频查找（X Bookmarks Short-Video Lookup）

> ⚠️ **每次运行必读**：先 `skill_view(name='x-bookmarks-short-video-lookup', file_path='references/core-workflow.md')` 加载完整工作流（数据源/信号识别/手动 5 步/pitfalls），再动手。换机安装见 `references/porting.md`。

## Layer map

| 层 | 文件 | 时机 |
|---|---|---|
| 核心工作流（必读） | `references/core-workflow.md` | 每次运行先加载 |
| 换机安装/移植 | `references/porting.md` | 迁移到新机器时 |
| 一键脚本 | `scripts/lookup_x_bookmark_videos.py` | 快速执行（推荐） |

## 快速使用

```bash
python3 <skill_dir>/scripts/lookup_x_bookmark_videos.py --minutes 10
```

扫描知识库每日 X bookmarks 全部批次 → bird CLI 逐条取 `durationMs` →
输出短视频（≤10min）/长视频/已删/外部链接四类清单，按视频推文 id 去重。

- 默认数据源：`<vault>/01_raw/notes/x-bookmarks/*-smaug-bookmarks-batch-prepared.json`
  （`<vault>` 默认 `/root/obsidianHermes`，可用 `--bookmarks-dir` 覆盖）
- 依赖：`bird` CLI（本机 `/usr/local/bin/bird`，需已认证）；脚本会自动检测并报错提示
- 62 个唯一视频约 90 秒跑完；全量结果落 `/tmp/x_bookmark_videos.json`

## Hard rules

1. prepared JSON `media` 字段恒空——视频信号只在 `links[]` 里：`/video/` URL = X 视频，`type=video` = 外部视频
2. link URL 字段名三选一兜底：`url`/`expanded`/`original`
3. `type=media` 混有图片——只有 `/video/` 才是视频
4. 同视频被多天批次重复收藏（5-19~5-22 连抓）→ 按视频推文 id 去重
5. `xurl` 未注册 app 会 401——直接走 bird；bird 读已删推文返回空 → 标「已删」，不重试
6. YouTube 反爬（yt-dlp/innertube/curl 都拦）→ 用 oEmbed 拿标题 + web_extract 抓章节判断时长

## Out of scope / do not use

- Should not trigger on: 找收藏里的文章/链接/文字（无视频意图）、X 全网视频搜索（那是 x-video-collect）
- do not use for: 视频下载/剪辑/转录；非知识库 bookmarks 来源的推文列表
- 外部视频链接（YouTube 频道页/长节目）不算短视频，单独列出不混入

## Dependencies

- `bird` CLI（必装）：`/usr/local/bin/bird`，认证后可用。缺失时脚本输出安装提示并退出
- 可选：`curl`（YouTube oEmbed 标题查询）
- 知识库路径可变：`--bookmarks-dir` 覆盖，不硬编码其他机器路径

## See also

- 相关技能：xurl（官方 API，未配置时不可用）、x-video-collect（X 全网视频搜索，不同场景）、smaug-bookmarks-obsidian-ingest（bookmarks 摄入管线）
- 触发评测：`python3 ~/.hermes/skills/yao-meta-skill/scripts/trigger_eval.py --description-file <SKILL.md> --cases evals/trigger_cases.json --semantic-config evals/semantic_config.json`
- Skill IR：`reports/skill-ir.json`（YAO export_skill_ir 产物）

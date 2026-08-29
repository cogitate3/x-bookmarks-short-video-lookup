# 移植到另一台机器（Porting Guide）

本 skill 依赖 **bird CLI**（X 内部 GraphQL 接口，非官方 API），换机后必须
重装 + 认证。以下是三步迁移法。

## 1. 拷贝 skill

```bash
# 源机
scp -r ~/.hermes/skills/social-media/x-bookmarks-short-video-lookup \
  user@newhost:~/.hermes/skills/social-media/

# 或通过 git 仓库（推荐，见发布流程）：npx skills add <user>/<repo> --skill x-bookmarks-short-video-lookup
```

## 2. 安装 bird CLI

```bash
# bird 是 Node CLI（v0.8.0），本机装于 /usr/local/bin/bird
npm install -g bird-cli   # 包名以实际发布名为准；源机执行 `which bird` / `bird --version` 确认来源
bird --help               # 验证可执行
```

> 若源机 bird 是 pipx/brew/go 安装，路径不同——迁移前先 `which bird` 确认，
> 把对应安装方式写进本文件。

## 3. bird 认证（关键）

bird 走 X 登录态（GraphQL），需要 cookie。三种来源：

```bash
# a) 显式传 cookie（推荐脚本场景）
bird --auth-token <auth_token> --ct0 <ct0> read <tweet_id> --json

# b) 浏览器 profile 自动提取
bird --chrome-profile <profile-name> read <tweet_id> --json

# c) 环境变量
export BIRD_AUTH_TOKEN=... BIRD_CT0=...
```

认证验证：`bird read <任意视频推文id> --json` 应返回含 `media[].durationMs` 的 JSON；
返回 `empty` 或 401 = cookie 失效，需重新导出（Cookie-Editor 浏览器扩展 → 导出
`auth_token` + `ct0`）。

## 4. 路径适配

- 脚本默认 `<vault>` = `/root/obsidianHermes`，其他机器用：
  `python3 .../lookup_x_bookmark_videos.py --bookmarks-dir /path/to/vault/01_raw/notes/x-bookmarks`
- 或改脚本顶部 `DEFAULT_DIR` 常量

## 5. 验证闭环

```bash
python3 ~/.hermes/skills/social-media/x-bookmarks-short-video-lookup/scripts/lookup_x_bookmark_videos.py --minutes 10
# 期望：扫描 N 条视频记录 → 输出短视频/长视频/已删/外部链接四类
# 若 bird 未认证：脚本报错提示 → 回到第 3 步
```

## 6. 环境坑（2026-08-28 实测）

- **bird 必须在有 X cookie 环境变量的 shell 里跑**：`TWITTER_AUTH_TOKEN` + `TWITTER_CT0`。
  Hermes 的 execute_code 工具环境**没有**这两个变量（terminal 有）——在 execute_code 里跑
  批量查询会全部返回「No Twitter cookies found」→ 结果全 none（看起来像推文被删，其实是认证缺失）。
  排查时先验证：`python3 -c "import os; print(bool(os.environ.get('TWITTER_AUTH_TOKEN')))"`。
- **X 批量限流**：287 条连续查询时后半段全挂（返回空）。脚本已内置重试（单条 2 次）+
  连续 15 条失败判定限流自动降速。若仍有大量 none，可 `--minutes` 分批或增大 sleep。
- **分类变化根因**：7-01 起 X 平台改了 t.co 短链重定向（不再暴露 /video/ 路径），
  smaug 摄入把所有视频链接标成 tweet。本 skill 的扫描已补偿（tweet 链接也纳入候选）。

## 已知依赖版本

- bird v0.8.0（2026-08 实测），命令：`bird read <id> --json`
- python3 ≥ 3.8（无第三方依赖，纯 stdlib）

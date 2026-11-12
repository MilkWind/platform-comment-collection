# 视频评论与弹幕采集 (platform-comment-collection)

[English](README.en.md) · **简体中文**

一个**迷你但实用**的插件式工具，用于采集视频平台的**评论**与**弹幕**。目前支持哔哩哔哩（B站），后续可扩展抖音等平台。

## 三种使用方式

同一个项目，同一份源码，三种用法：

1. **内置界面（推荐新手）** —— 本地网页应用：选择平台 → 粘贴视频链接 →（可选）一键获取 Cookie → 勾选字段 → 开始采集 → 查看进度与日志 → 下载结果。
2. **Skill（面向 AI Agent）** —— `skills/bilibili/` 是自包含的技能目录，Agent 可加载 `SKILL.md` 按流程操作。
3. **复制核心** —— 直接把 `skills/bilibili/core/bilicrawl/` 整个文件夹拷进你自己的项目，调用核心 API 即可。它只依赖标准库 + `requests` + `protobuf`。

项目结构遵循：`{[(核心 py 文件) 技能封装] 附加界面}`。多平台时即：`{[(各平台核心) 各平台技能] 统一多标签界面}`。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/) 与 Python ≥ 3.12。

```bash
uv sync

# 1) 内置网页界面
uv run streamlit run app/streamlit_app.py

# 2) 命令行无界面采集
uv run python examples/run_engine_headless.py BV1GJ411x7h7 --max-roots 40

# 3) 只用核心 API 的示例
uv run python skills/bilibili/examples/quickstart.py BV1GJ411x7h7
```

## 设计要点

- **核心只管 API**：每个核心方法至多发起一次 HTTP 请求，不 sleep、不重试、不写文件。见 [`docs/adapter-contract.md`](docs/adapter-contract.md)。
- **策略在外层**：限速、退避、断点续传、去重、多P处理等抽象策略写在 `skills/bilibili/references/strategies.md`，由 `app/engine/` 实现。
- **统一可扩展**：新增平台只需 `skills/<platform>/`（复制 `skills/_template/`），界面标签会自动出现，无需修改 `app/`。
- **认证可选**：匿名即可采集评论与弹幕；登录后可获得 IP 属地并更完整地抓取楼中楼。

## 关于 Cookie（可选）

在已登录的 `bilibili.com` 页面打开开发者工具控制台，运行 `skills/bilibili/scripts/sessdata_snippet.js` 中的片段即可复制 `SESSDATA`。若提示 `SESSDATA` 为 HttpOnly，请在「网络」面板中任选一个 `api.bilibili.com` 请求 → 右键 → 复制为 cURL，然后粘贴到应用里。**无需** `bili_jct`，所有操作均为只读。

## 目录结构

```
app/        外层：引擎（策略实现）+ Streamlit 界面
skills/     技能：每个平台一个目录
  bilibili/   SKILL.md + references/ + core/bilicrawl/(可复制核心)
  _template/  新平台的脚手架
docs/       适配器契约与架构说明
scripts/    生成 protobuf、在线冒烟测试
tests/      离线单元测试（固定夹具，不联网）
```

## 输出

```
output/bilibili/<BV号>/
├── comments.csv / comments.jsonl
├── danmaku.csv  / danmaku.jsonl
├── meta.json
└── checkpoint.json
```

CSV 使用 `utf-8-sig` 编码，Excel 可直接正确显示中文。

## 测试

```bash
uv run pytest -q                                   # 离线单元测试
uv run python scripts/live_smoke.py --bvid BV1GJ411x7h7   # 联网冒烟测试（手动）
```

## 许可证

MIT，见 [LICENSE](LICENSE)。

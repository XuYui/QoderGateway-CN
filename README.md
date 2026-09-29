<h1 align="center">QoderGateway CN</h1>

<p align="center">
  基于 QoderGateway 的 Qoder CN 兼容网关。<br>
  A Qoder CN compatible fork of QoderGateway with an OpenAI-compatible API.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?logo=python&logoColor=white" alt="Python >= 3.11">
  <img src="https://img.shields.io/badge/fastapi-0.115+-green?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
  <a href="https://linux.do"><img src="https://img.shields.io/badge/LINUX_DO-%E7%A4%BE%E5%8C%BA-blue" alt="LINUX DO"></a>
</p>

---

## 本分支说明 / Fork Notes

本项目基于 [bzym2/QoderGateway](https://github.com/bzym2/QoderGateway)，保留原项目的 MIT 许可证，并补充了 Qoder CN 适配：

- 使用 `gateway.qoder.com.cn` 的 PAT 鉴权接口
- 使用 Qoder CN 的 COSY 签名、请求编码和 Agent Chat SSE 协议
- 将 OpenAI/Pi 的 `developer` 消息角色转换为 Qoder 支持的 `system`
- 增加 `/v1/models` 和 `/models` 模型列表接口
- 修复 Linux 环境下的 Windows-only 依赖安装问题

This repository is based on [bzym2/QoderGateway](https://github.com/bzym2/QoderGateway). The upstream MIT license is retained. The fork adds Qoder CN authentication and Agent Chat compatibility, OpenAI/Pi message-role conversion, model discovery endpoints, and Linux installation fixes.

## Qoder CN 配置 / Qoder CN Setup

在 Qoder 的 [Account Integrations](https://qoder.cn/account/integrations) 创建 PAT，并在管理控制台导入。PAT、管理员密码和 API Key 只应保存在本地或服务器环境变量中，不要提交到 Git 仓库。

The core chat path is tested with Qoder CN PAT accounts. Token refresh behavior may vary as Qoder changes its regional authentication endpoints; re-import the PAT from the console if a stored session expires.

## 安全发布 / Safe Publishing

Never commit `.env`, PATs, API keys, administrator passwords, SQLite databases, TLS private keys, or server-specific configuration. The repository includes ignore rules for these files; review `git diff --cached` before pushing.

## 致谢 / Acknowledgment

本项目思路来源于 [cubk1/qoder2api](https://github.com/cubk1/qoder2api/)，在此基础上用 Python 重写了后端并新增了 WebUI 管理控制台、SQLite 持久化、多账号池轮转和独立文档站。

This project is inspired by [cubk1/qoder2api](https://github.com/cubk1/qoder2api/). We rewrote the backend in Python and added a WebUI management console, SQLite persistence, multi-account pool rotation, and a standalone documentation site.

特别感谢 [LINUX DO](https://linux.do) 社区提供的交流与推广平台。

Special thanks to the [LINUX DO](https://linux.do) community for the platform of exchange and promotion.

## 功能 / Features

- **OpenAI 兼容接口** — 通过 `/v1/chat/completions` 向客户端提供标准 Chat Completions API
- **多账号池** — 导入多个 Qoder 账号，按 UID 自动去重，请求失败时自动轮转
- **两层鉴权** — 管理后台密钥与外部 API Key 分开配置
- **SQLite 持久化** — 账号、API Key、全局配置全部存入本地数据库
- **WebUI 控制台** — Dashboard、账号管理、API Key 管理、Playground、服务日志
- **独立文档站** — `/documents` 提供中英文 Wiki，支持本地搜索和目录跳转
- **自动检测语言** — 根据浏览器地区自动切换中文/英文

## 快速开始 / Quickstart

### 安装 / Install

```bash
git clone https://github.com/XuYui/QoderGateway-CN.git
cd QoderGateway-CN
uv sync
```

### 前端构建 / Build Frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

构建产物会输出到 `src/qoder2api/static/`，后端启动时直接托管 WebUI 与文档站。

### 配置 / Configure

```bash
cp .env.example .env
```

编辑 `.env`，修改管理员密码：

```env
QODER_ADMIN_PASSWORD=your-strong-password
```

> **默认密码是 `admin`，强烈建议第一次登录后立即修改。**

### 启动 / Start

```bash
uv run qoder2api
```

服务默认运行在 `http://127.0.0.1:5050/`。

| 路径 | 说明 |
|------|------|
| `/` | Landing Page |
| `/console` | 管理控制台 |
| `/documents` | 文档站 / Wiki |
| `/v1/chat/completions` | OpenAI 兼容 API |
| `/v1/models` | OpenAI 兼容模型列表 |

### 第一次 API 调用 / First API Call

在控制台导入账号后：

```bash
curl http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lite",
    "messages": [{ "role": "user", "content": "Hello" }],
    "stream": false
  }'
```

## 环境变量 / Environment Variables

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QODER_HOST` | 服务绑定地址 | `127.0.0.1` |
| `QODER_PORT` | 服务端口 | `5050` |
| `QODER_ADMIN_PASSWORD` | 管理员密码（覆盖 SQLite 存储值） | `admin` |
| `QODER_PROXY` | 出站代理地址 | 空 |
| `QODER_ENABLE_DOCUMENTS` | 是否启用文档页 | `1` |
| `QODER_ENABLE_LANDING` | 是否启用 Landing Page | `1` |
| `QODER_PAT` | 首次启动时自动导入的 PAT | 空 |

## 项目结构 / Project Structure

```
├── src/qoder2api/          # Python 后端
│   ├── app.py              # FastAPI 路由
│   ├── accounts.py         # SQLite 账号管理
│   ├── auth.py             # Qoder 鉴权与签名
│   ├── bridge.py           # OpenAI 兼容响应转换
│   ├── config.py           # 配置读写
│   ├── database.py         # SQLite schema
│   ├── env.py              # 环境变量加载
│   └── static/             # 前端构建产物
├── frontend/               # React 前端源码
│   ├── src/App.tsx         # 管理控制台
│   ├── src/docs-main.tsx   # 文档站
│   ├── src/landing-main.tsx# Landing Page
│   └── src/docs/           # 中英文 Markdown 文档
├── .env.example            # 环境变量模板
└── pyproject.toml          # 项目配置
```

## License

MIT

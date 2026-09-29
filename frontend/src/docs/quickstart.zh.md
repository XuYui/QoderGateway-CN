# 快速入门

本页说明如何从零启动 QoderGateway，管理 Qoder 账号，并完成第一次 API 调用。

## 快速入门

按顺序完成这三步：

- 启动 QoderGateway。
- 管理 Qoder 账号与请求路由。
- 完成第一次 OpenAI 兼容 API 调用。

## 安装并启动

先克隆仓库并安装依赖：

```bash
git clone https://github.com/bzym2/QoderGateway.git
cd QoderGateway
uv sync
```

然后启动服务：

```powershell
uv run qoder2api
```

WebUI 地址：

```text
http://127.0.0.1:5050/
```

## 登录与修改默认密码

默认网关登录密钥是：

```text
admin
```

第一次启动后可以直接用 `admin` 登录控制台。

强烈建议你立刻修改默认密码。复制环境变量模板：

```bash
mv .env.example .env
```

然后在 `.env` 中设置管理员密码：

```env
QODER_ADMIN_PASSWORD=your-strong-password
```

这个密码用于保护所有 `/ui/*` 管理接口，前端会自动把它作为 `X-Gateway-Token` 发送。

## 管理 Qoder 账号

你可以使用两种方式：

- 点击 **Auto Import**，从本机 Qoder auth 会话自动导入。
- 在 **Add PAT** 中粘贴 Qoder Personal Access Token。

导入后的账号会存入本地 SQLite，并按 `uid` 自动去重。

## 完成第一次 API 调用

账号就绪后，可以发送 Chat Completions 请求：

```bash
curl http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lite",
    "messages": [{ "role": "user", "content": "Say hello" }],
    "stream": false
  }'
```

如果你开启了 API Key 鉴权，还需要额外传入：

```bash
-H "Authorization: Bearer <your-api-key>"
```

## 验证请求路由

打开 **Service Logs**，每次请求都会打印它被路由到哪个账号：

```text
Request routing via account: Alice (019ec5c6-4bb0-7c1c-bf93-5209e1367f2b)
```

## 下一步

- 如果要开放给其他机器使用，先阅读 **鉴权机制**。
- 如果要理解自动切换账号，阅读 **账号池**。
- 如果要接入 OpenAI SDK，阅读 **API 参考**。

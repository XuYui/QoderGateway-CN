# 运维

本页记录本地运行 QoderGate 时最常用的维护动作。

## SQLite 存储位置

QoderGate 的运行数据保存在：

```text
~/.qoder/qoder2api.db
```

数据库包含账号、允许的 API Key 和全局设置。

## 备份

停止服务后复制数据库文件：

```powershell
Copy-Item "$env:USERPROFILE\.qoder\qoder2api.db" "$env:USERPROFILE\Desktop\qoder2api.db.backup"
```

## 重置 Gateway Token

网关 Token 保存在 `settings` 表里的 `gateway_token` 字段。

如果忘记密钥，可以直接修改 SQLite，或者删除数据库让程序重新初始化默认配置。

## 常见问题

### 401 Unauthorized

- 管理接口：检查 `X-Gateway-Token`。
- API 接口：检查 `Authorization: Bearer <key>`。

### No Active Session

在 Dashboard 导入账号或添加 PAT。

### Account Quota Exceeded

禁用额度耗尽的账号，或者导入更多账号让自动轮转继续工作。

### Local Auth Import Failed

确认本机已经登录过 Qoder CLI，并且本地 auth 文件存在。

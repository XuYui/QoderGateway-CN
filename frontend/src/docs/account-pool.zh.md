# 账号池

账号池让 QoderGate 可以通过多个 Qoder 账号处理请求，并在某个账号失败时自动切换到其他账号。

## 导入方式

### Auto Import

读取当前机器上的 Qoder 本地登录会话，并导入 SQLite。

### Add PAT

通过 Qoder Personal Access Token 换取可用会话，并保存到账号池。

## 自动去重

账号按 `uid` 去重。重复导入同一个用户时，会更新会话数据，而不是创建重复账号。

## 启用和禁用

禁用的账号仍保留在 SQLite 中，但不会参与请求路由。

## Active Account

Active 账号会作为请求的第一候选。若请求失败，QoderGate 会自动轮转到其他启用账号。

## 额度字段

| 字段 | 含义 |
| --- | --- |
| `quota` | Qoder 返回的当前额度值。 |
| `is_quota_exceeded` | 账号是否已经超出额度。 |
| `plan` | 账号套餐标识。 |
| `user_tag` | Qoder 返回的展示标签。 |
| `next_reset_at` | 额度预计重置时间。 |

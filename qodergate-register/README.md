# qodergate-register

Qoder 独立注册机：无限循环注册（母线程 × 3 子任务并发），浏览器隐藏后台、
人机验证置顶一次，划完自动轮到下一个；每个成功注册自动**导出 JSON**。

> 从 QoderGateway 的注册机模块独立提取，无网关依赖。

## 安装

```bash
cd qodergate-register
uv sync          # 或 pip install -e .
```

## 配置

```bash
# 项目根 .env 或环境变量
YYDS_API_KEY=AC-xxx
```

## 使用

```bash
uv run python -m qodergate_register --check              # 检查配置
uv run python -m qodergate_register --parents 2          # 2 个母线程（每批 3 子任务并发）
uv run python -m qodergate_register --parents 1 --output ./out.json
# Ctrl+C 停止（当前批次完成后停止并打印统计）
```

## 导出格式（accounts.json）

```json
[
  {
    "email": "qoderxxx@td3.mom",
    "password": "...",
    "name": "...",
    "user_id": "019f...",
    "token": "dt-...",
    "refresh_token": "drt-...",
    "expires_at": "2026-09-05T...Z",
    "refresh_token_expires_at": "2027-08-01T...Z",
    "exported_at": "..."
  }
]
```

可直接导入 QoderGateway 账号池（批量添加）。

## 说明

- 人机验证（阿里云滑块）需人工完成：窗口平时隐藏，验证时置顶弹出，划完自动隐藏。
- 每母线程每批 3 个子任务并发；批内 2s 错峰，保证验证时间错开、连续可划。
- 遵守 Qoder 服务条款，控制使用频率。

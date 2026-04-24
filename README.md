# Dashboard - 部署调度管理面板
- 以下内容主要针对dashboard/下的内容介绍！
- 基于 FastAPI 的轻量级管理面板，提供品牌订阅管理、SQL 脚本执行、系统配置、数据清洗监控和 Parquet 文件解析等功能。

## 功能概览

| 页面 | 说明 |
|------|------|
| 品牌订阅列表 | 查看/推进品牌订阅状态，新增合约（一次性写入 7 张表） |
| 品牌脚本执行 | 在品牌 Doris 数据源上执行 SQL，支持占位符模板和高危语句拦截 |
| 红盘系统配置 | 系统配置项的增删改查 |
| 每日清洗监控 | 查看数据清洗任务进度，对失败任务进行重试 |
| Parquet 文件解析 | 上传并预览 Parquet 文件内容（最大 30MB，返回前 500 行） |

<img width="1920" height="869" alt="image" src="https://github.com/user-attachments/assets/148b4f49-9998-47c9-9420-5895f2ea8179" />
<img width="1920" height="869" alt="image" src="https://github.com/user-attachments/assets/beca7f09-f206-480c-a79b-5066a2bc1fbe" />
<img width="1920" height="869" alt="image" src="https://github.com/user-attachments/assets/f0245a26-6f88-4934-aaf2-a383dca9e034" />
<img width="1920" height="869" alt="image" src="https://github.com/user-attachments/assets/ee8f96e5-66ec-40ad-90c1-c0920d849e62" />
<img width="1920" height="869" alt="image" src="https://github.com/user-attachments/assets/f53b361e-e67b-45a6-9866-bd398009998b" />


## 快速启动

### 本地开发

```bash
# 安装项目依赖
pip install -e ".[dev]"

# 启动 dashboard（默认 http://127.0.0.1:8001）
xhs-crawler dashboard

# 自定义参数
xhs-crawler dashboard --host 0.0.0.0 --port 8080 --reload --verbose
```

### Docker 部署

```bash
docker build -t xhs-dashboard .
docker run -d \
  -p 8000:8000 \
  -e DASHBOARD_DB_HOST=your-db-host \
  -e DASHBOARD_DB_NAME=your-db-name \
  -e DASHBOARD_DB_USER=root \
  -e DASHBOARD_DB_PASSWORD=secret \
  xhs-dashboard
```

## CLI 参数

```
xhs-crawler dashboard [OPTIONS]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `127.0.0.1` | 绑定地址 |
| `--port`, `-p` | `8001` | 绑定端口 |
| `--reload` | `False` | 启用热重载（开发模式） |
| `--verbose`, `-v` | `False` | 开启 DEBUG 日志 |

## 环境变量

### 数据库连接

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DASHBOARD_DB_HOST` | — | MySQL 地址（必填） |
| `DASHBOARD_DB_PORT` | `3306` | MySQL 端口 |
| `DASHBOARD_DB_NAME` | — | 数据库名（必填） |
| `DASHBOARD_DB_USER` | — | 数据库用户（必填） |
| `DASHBOARD_DB_PASSWORD` | — | 数据库密码（必填） |

### 认证与安全

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DASHBOARD_USERNAME` | `admin` | 登录用户名 |
| `DASHBOARD_PASSWORD` | `admin` | 登录密码 |
| `SCRIPT_PRIVILEGED_PASSWORD` | — | 高危 SQL 执行密码，未配置则禁止执行高危语句 |

### Docker 部署

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DASHBOARD_HOST` | `0.0.0.0` | 容器内绑定地址 |
| `DASHBOARD_PORT` | `8000` | 容器内绑定端口 |

## API 接口

### 公开接口（无需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查，返回 `{"status": "ok"}` |
| GET | `/login` | 登录页面 |
| POST | `/api/login` | 用户登录 |
| POST | `/api/logout` | 用户登出 |

### 订阅管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/subscriptions` | 获取品牌订阅列表 |
| POST | `/api/subscriptions/{sub_id}/advance` | 推进订阅状态（1→2→3） |
| POST | `/api/contracts` | 新增合约 |

### SQL 脚本执行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/scripts/execute` | 在品牌 Doris 数据源执行 SQL |

SQL 允许的语句类型：`SELECT`、`INSERT`、`UPDATE`、`DELETE`、`SHOW`、`EXPLAIN`。其他语句需提供高权限密码。

### 系统配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sys_configs` | 获取配置列表 |
| POST | `/api/sys_configs` | 新增配置 |
| PUT | `/api/sys_configs/{config_id}` | 更新配置 |
| DELETE | `/api/sys_configs/{config_id}` | 删除配置（逻辑删除） |

### 清洗任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/clean_tasks` | 获取清洗任务列表 |
| POST | `/api/clean_tasks/{task_id}/retry` | 重试失败任务（状态 3→0） |

### Parquet 解析

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/parquet/parse` | 上传并解析 Parquet 文件 |

## 项目结构

```
dashboard/
├── app.py              # FastAPI 应用主入口，路由和中间件
├── models.py           # Pydantic 数据模型
├── database.py         # MySQL 连接池管理
├── task_manager.py     # 数据库查询/变更逻辑
├── templates/
│   ├── index.html      # 主页面（5 个功能页签）
│   └── login.html      # 登录页面
└── static/
    ├── css/
    │   └── dashboard.css
    └── js/
        └── dashboard.js
```

## 认证机制

- 基于 Cookie 的会话认证，会话有效期 1 小时
- 登录后服务端生成随机 token，通过 `dash_token` HttpOnly Cookie 下发
- 所有非公开路径的请求均需携带有效 Cookie，否则 API 返回 401、页面重定向到 `/login`

## Docker 健康检查

推荐在 Dockerfile 或 docker-compose 中配置：

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

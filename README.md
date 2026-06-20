# ForgeFlow AI 🚀

**AI After-Sales Workforce for E-commerce**

> 让电商售后处理效率提升10倍——通过AI Agent自动处理80%的售后工单

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14.2+-black.svg)](https://nextjs.org)

---

## 项目简介

ForgeFlow AI 是一个面向 Shopify 中小商家的 AI 售后运营智能体平台。
不同于传统 AI 客服机器人，ForgeFlow 定位为 **"AI 售后运营 Agent"**——
它能自动完成查询→判断→执行的完整闭环，而不仅仅是话术回复。

### V1 核心能力

- 🎯 **3个核心售后场景**: 物流延迟、退款申请、异常订单（损坏/发错）
- 🤖 **自动解决率 ≥ 60%**: 80%的重复性工单自动处理
- ⚡ **平均处理时间 ≤ 5秒**: 从客户咨询到自动执行
- 🔒 **Human-in-the-Loop**: 高风险操作自动进入人工审批流

## 技术架构

```
┌─────────────────────────────────────────┐
│         Frontend: Next.js 14.2+         │
│   Dashboard │ Tickets │ Approval │ KB   │
└──────────────────┬──────────────────────┘
                   │ HTTPS / WebSocket
┌──────────────────▼──────────────────────┐
│      Backend: FastAPI + LangGraph       │
│   Intent → Order → Logistics → Policy  │
│              → Decision → Execute       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│   Data: PostgreSQL(pgvector) + Redis    │
│   LLM: OpenAI / Anthropic / Qwen       │
└─────────────────────────────────────────┘
```

## 快速开始

### 前置条件

- **Docker Desktop** (PostgreSQL + Redis)
- **Python 3.11+** + [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** + [pnpm](https://pnpm.io/) 9+

### 1. 克隆与安装

```bash
git clone <repo-url> forgeflow
cd forgeflow

# 安装依赖
pnpm setup        # 前端 + 后端所有依赖
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Keys
```

### 3. 启动开发环境

```bash
# 启动数据库
pnpm docker:up

# 运行数据库迁移
pnpm db:migrate

# 启动开发服务器（API + Web）
pnpm dev
```

访问:
- **前端**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

### 4. 关闭

```bash
pnpm docker:down
```

## 项目结构

```
forgeflow/
├── apps/
│   ├── api/                    # Python FastAPI 后端
│   │   ├── src/forgeflow/
│   │   │   ├── core/           # 配置、安全
│   │   │   ├── db/             # 数据库、迁移
│   │   │   ├── models/         # ORM 模型
│   │   │   ├── api/            # REST 路由
│   │   │   ├── providers/      # 平台抽象层
│   │   │   ├── llm/            # LLM 抽象层
│   │   │   ├── agent/          # Agent 运行时
│   │   │   └── monitoring/     # 日志、追踪、指标
│   │   └── tests/
│   └── web/                    # Next.js 前端
│       └── src/
│           ├── app/            # App Router 页面
│           ├── components/     # UI 组件
│           └── lib/            # 工具库
├── db/init/                    # 数据库初始化
├── docker-compose.yml
└── docs/                       # 文档
```

## 开发指南

### 常用命令

| 命令 | 说明 |
|------|------|
| `pnpm dev` | 启动全栈开发服务器 |
| `pnpm lint` | 运行所有 linter |
| `pnpm test` | 运行所有测试 |
| `pnpm db:migrate` | 数据库迁移 |
| `pnpm docker:up` | 启动 Docker 服务 |

### 代码规范

- **Python**: ruff (lint + format) + mypy (type check)
- **TypeScript**: Biome (lint + format)
- **提交**: 遵循 [Conventional Commits](https://www.conventionalcommits.org/)

## 开发阶段

| Phase | 周期 | 目标 |
|-------|------|------|
| **Phase 0** 🟢 | Week 1-2 | 基础设施搭建 |
| **Phase 1** | Week 3-5 | Agent 核心引擎 |
| **Phase 2** | Week 6-7 | 前端工作台 |
| **Phase 3** | Week 8-9 | 知识库与增强 |
| **Phase 4** | Week 10-11 | 测试与优化 |
| **Phase 5** | Week 12-13 | 试点上线 |

## 文档

- [完整 PRD (V1.1)](../ForgeFlow_AI_PRD_V1.1.md)
- [API 文档](http://localhost:8000/docs) (开发环境)
- [CLAUDE.md](CLAUDE.md) — AI 助手上下文

## License

MIT © 2026 ForgeFlow AI

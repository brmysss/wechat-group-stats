# Phase 1：数据管道 + Web Dashboard

> **For Hermes:** 用 Claude Code delegate_task 逐 task 实施。

**Goal:** 把微信群聊数据从本地脚本变成一个 Web 平台。Phase 1 完成基础设施：邀请码登录、数据同步管道、基础 Dashboard。

**Architecture:** Next.js 14 App Router + Tailwind + shadcn/ui → Prisma ORM → Supabase PostgreSQL。数据采集仍走本地 Python 脚本（已有的 wechat-stats.py 增强），通过 Hermes cron 定时推送到 API。

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Prisma, Supabase (PostgreSQL), Python (数据采集)

---

## 邀请码登录流程

```
管理员(2898) → 后台生成邀请码 → 微信私发成员
成员 → 打开网页 → 输入邀请码 + 设用户名 → 创建账号
```

- 邀请码一次性，用完即焚
- 不需要微信 OAuth，零审核零费用
- 后期可在后台手动绑定 wxid（关联 WeChat 身份）

## 数据流

```
2898 Mac (Hermes cron 每30分钟)
  └→ wechat-stats.py --push → POST /api/messages/sync (API Key 认证)
      └→ Supabase PostgreSQL
          └→ Web Dashboard 实时展示
```

---

## 数据库 Schema

```
User
  id            String   @id @default(uuid())
  username      String   @unique        # 用户自设
  displayName   String                  # 展示名
  inviteCode    String   @unique        # 注册时用的邀请码
  wxid          String?                 # 微信ID（后期绑定）
  createdAt     DateTime @default(now())

InviteCode
  id            String   @id @default(uuid())
  code          String   @unique        # 8位随机码
  isUsed        Boolean  @default(false)
  usedBy        String?                 # → User.id
  createdBy     String                  # 谁生成的
  createdAt     DateTime @default(now())

ApiKey
  id            String   @id @default(uuid())
  key           String   @unique        # 用于脚本认证
  label         String                  # 标识（如 "2898 Mac Studio"）
  createdAt     DateTime @default(now())

Group
  id            String   @id @default(uuid())
  wxGroupId     String   @unique        # 45379818937@chatroom
  name          String                  # 链上前进四🚀

Message
  id            String   @id @default(uuid())
  groupId       String                  # → Group.id
  senderWxid    String                  # 发送者微信ID
  content       String                  # 消息全文
  sentAt        DateTime                # 微信原始时间戳
  ingestedAt    DateTime @default(now())

Cycle
  id            String   @id @default(uuid())
  name          String                  # "2026-W24"
  groupId       String
  startDate     DateTime
  endDate       DateTime
  status        String   @default("active")  # active | closed

Score                            # Phase 2 开始用
  id            String   @id @default(uuid())
  userId        String
  cycleId       String
  activePoints  Int      @default(0)
  sharerPoints  Int      @default(0)
  researcherPoints Int   @default(0)
  collaboratorPoints Int @default(0)
  dragonBalls   Int      @default(0)
```

---

## API 设计

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| POST | `/api/auth/invite` | 无 | 邀请码验证 + 注册 → set cookie |
| GET | `/api/auth/me` | Cookie | 当前用户信息 |
| POST | `/api/admin/invite-codes` | Admin | 批量生成邀请码 |
| GET | `/api/admin/invite-codes` | Admin | 查看所有邀请码 |
| POST | `/api/messages/sync` | API Key | 脚本推送消息 |
| GET | `/api/stats?groupId=xxx` | Cookie | 群成员统计数据 |

---

## 页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 登录页 | 输入邀请码 → 设用户名 → 进 Dashboard |
| `/dashboard` | Dashboard | 排行榜、活跃分布、消息趋势（需登录） |
| `/dashboard/me` | 个人中心 | 我的积分、发言统计 |
| `/admin` | 管理后台 | 生成邀请码、查看同步状态（仅 admin） |

---

## 文件结构

```
wechat-group-stats/           ← 现有 repo，添加 Next.js
├── app/                      ← NEW: Next.js App Router
│   ├── layout.tsx
│   ├── page.tsx              # 登录页
│   ├── dashboard/
│   │   ├── page.tsx          # 主面板
│   │   └── me/
│   │       └── page.tsx      # 个人中心
│   ├── admin/
│   │   └── page.tsx          # 管理后台
│   └── api/
│       ├── auth/
│       │   ├── invite/route.ts
│       │   └── me/route.ts
│       ├── admin/
│       │   └── invite-codes/route.ts
│       ├── messages/
│       │   └── sync/route.ts
│       └── stats/
│           └── route.ts
├── components/
│   ├── ui/                   # shadcn components
│   ├── login-form.tsx
│   ├── leaderboard.tsx
│   ├── stats-cards.tsx
│   └── nav.tsx
├── lib/
│   ├── prisma.ts
│   ├── auth.ts               # cookie session
│   └── api-key.ts
├── prisma/
│   └── schema.prisma
├── scripts/                  # Python 脚本（迁移进来）
│   ├── wechat-stats.py       # 增强版：加 --push 模式
│   └── sync.py               # 独立同步脚本
├── .env.example
├── package.json
├── tailwind.config.ts
├── tsconfig.json
├── ecosystem.config.cjs      # 已有，pm2 配置
├── wechat-stats.py           # 保持兼容
├── wechat-server.py          # 保持兼容（本地仍可用）
└── dashboard.html            # 保留（向后兼容）
```

---

## 实施任务

### Task 1: 初始化 Next.js 项目

```
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir=false
npx shadcn@latest init
```

### Task 2: 配置 shadcn/ui + 基础布局

添加组件：Button, Input, Card, Table, Badge, Tabs, Dialog, Toast

### Task 3: Supabase + Prisma 配置

- 创建 Supabase 项目
- 写 Prisma schema
- `npx prisma db push`

### Task 4: 邀请码生成 + 验证 API

- POST /api/admin/invite-codes（生成 N 个邀请码）
- POST /api/auth/invite（验证 + 注册 + set cookie）

### Task 5: 登录页面

漂亮的邀请码输入页 → 验证 → 设用户名 → 跳转 Dashboard

### Task 6: 消息同步 API

- POST /api/messages/sync（API Key 认证，批量写入）
- 去重逻辑（相同 wxid + sentAt + groupId 不重复插入）

### Task 7: 增强 wechat-stats.py（--push 模式）

在现有脚本上加 `--push` 参数：
- 解密 DB → 提取消息全文（不只是计数）
- 记录上次同步位置（last_synced 时间戳）
- 增量推送新消息到 API

### Task 8: Hermes Cron 定时同步

```
hermes cron create --schedule "30m" --prompt "运行 wechat-stats.py --push 推送到生产 API"
```

### Task 9: Dashboard 页面

- 统计卡片（总消息、活跃人数、本周新增）
- 排行榜（按消息数排序，带活跃标签）
- 搜索成员

### Task 10: 个人中心

- 我的发言统计（总数 / 近1月 / 近3月）
- 活跃标签
- 积分占位（显示 "Phase 2 即将上线"）

### Task 11: 管理后台

- 生成邀请码（输入数量 → 批量生成 → 复制列表）
- 邀请码使用状态
- 同步日志

### Task 12: Vercel 部署

- 推送代码到 GitHub
- Vercel 连接 repo → 自动部署
- 环境变量配置

---

## 不做的事（留给 Phase 2/3）

- ❌ AI 消息评分
- ❌ 积分系统（数据表预留）
- ❌ 双周周期结算
- ❌ 龙珠
- ❌ 奖励商城 / 抽奖
- ❌ 微信身份绑定（后台手动可选）

---

## 下一步确认

Phase 1 预计 **8-12 个 task**，完成后你有一个：
- ✅ 可访问的 Web Dashboard
- ✅ 邀请码控制的封闭社区
- ✅ 自动同步的群数据
- ✅ 数据库 ready for AI scoring

可以开始干了？

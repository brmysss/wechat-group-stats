-- 前进四社群 - 数据库建表 SQL
-- 复制到 Supabase SQL Editor 执行

CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "inviteCode" TEXT NOT NULL,
    "wxid" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "users_username_key" ON "users"("username");
CREATE UNIQUE INDEX "users_inviteCode_key" ON "users"("inviteCode");

CREATE TABLE "invite_codes" (
    "id" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "isUsed" BOOLEAN NOT NULL DEFAULT false,
    "usedBy" TEXT,
    "createdBy" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "invite_codes_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "invite_codes_code_key" ON "invite_codes"("code");

CREATE TABLE "api_keys" (
    "id" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "api_keys_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "api_keys_key_key" ON "api_keys"("key");

CREATE TABLE "groups" (
    "id" TEXT NOT NULL,
    "wxGroupId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    CONSTRAINT "groups_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "groups_wxGroupId_key" ON "groups"("wxGroupId");

CREATE TABLE "messages" (
    "id" TEXT NOT NULL,
    "groupId" TEXT NOT NULL,
    "senderWxid" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "sentAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "messages_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "messages_groupId_senderWxid_sentAt_key" ON "messages"("groupId", "senderWxid", "sentAt");
ALTER TABLE "messages" ADD CONSTRAINT "messages_groupId_fkey" FOREIGN KEY ("groupId") REFERENCES "groups"("id");

CREATE TABLE "cycles" (
    "id" TEXT NOT NULL,
    "groupId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "startDate" TIMESTAMP(3) NOT NULL,
    "endDate" TIMESTAMP(3) NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    CONSTRAINT "cycles_pkey" PRIMARY KEY ("id")
);
ALTER TABLE "cycles" ADD CONSTRAINT "cycles_groupId_fkey" FOREIGN KEY ("groupId") REFERENCES "groups"("id");

CREATE TABLE "scores" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "cycleId" TEXT NOT NULL,
    "activePoints" INTEGER NOT NULL DEFAULT 0,
    "sharerPoints" INTEGER NOT NULL DEFAULT 0,
    "researcherPoints" INTEGER NOT NULL DEFAULT 0,
    "collaboratorPoints" INTEGER NOT NULL DEFAULT 0,
    "dragonBalls" INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT "scores_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "scores_userId_cycleId_key" ON "scores"("userId", "cycleId");
ALTER TABLE "scores" ADD CONSTRAINT "scores_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id");
ALTER TABLE "scores" ADD CONSTRAINT "scores_cycleId_fkey" FOREIGN KEY ("cycleId") REFERENCES "cycles"("id");

CREATE TABLE "rewards" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "costPoints" INTEGER NOT NULL,
    "stock" INTEGER NOT NULL DEFAULT 0,
    "imageUrl" TEXT,
    "description" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "rewards_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "redemptions" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "rewardId" TEXT NOT NULL,
    "pointsSpent" INTEGER NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "shippingInfo" TEXT,
    "ethAddress" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "redemptions_pkey" PRIMARY KEY ("id")
);
ALTER TABLE "redemptions" ADD CONSTRAINT "redemptions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id");
ALTER TABLE "redemptions" ADD CONSTRAINT "redemptions_rewardId_fkey" FOREIGN KEY ("rewardId") REFERENCES "rewards"("id");

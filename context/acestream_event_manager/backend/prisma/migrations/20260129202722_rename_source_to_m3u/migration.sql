-- CreateTable
CREATE TABLE "EventSession" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "name" TEXT,
    "regexFilter" TEXT NOT NULL DEFAULT '.*',
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "channelId" INTEGER,
    CONSTRAINT "EventSession_channelId_fkey" FOREIGN KEY ("channelId") REFERENCES "Channel" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Channel" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "channelNumber" REAL
);

-- CreateTable
CREATE TABLE "Stream" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "channelId" INTEGER NOT NULL,
    "url" TEXT NOT NULL,
    "name" TEXT,
    "m3u_account" TEXT,
    "width" INTEGER,
    "height" INTEGER,
    "fps" REAL,
    "bitrate" INTEGER,
    "isQuarantined" BOOLEAN NOT NULL DEFAULT false,
    "quarantinedAt" DATETIME,
    "lastCheckedAt" DATETIME,
    CONSTRAINT "Stream_channelId_fkey" FOREIGN KEY ("channelId") REFERENCES "Channel" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "StreamHealth" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "streamId" TEXT NOT NULL,
    "timestamp" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "speed" REAL,
    "peers" INTEGER,
    "failed" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "StreamHealth_streamId_fkey" FOREIGN KEY ("streamId") REFERENCES "Stream" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Preset" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "name" TEXT NOT NULL,
    "channelId" INTEGER NOT NULL,
    "regexFilter" TEXT NOT NULL DEFAULT '.*',
    "timeoutMs" INTEGER NOT NULL DEFAULT 30000,
    "staggerMs" INTEGER NOT NULL DEFAULT 200
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_EventSession" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "name" TEXT,
    "regexFilter" TEXT NOT NULL DEFAULT '.*',
    "timeoutMs" INTEGER NOT NULL DEFAULT 30000,
    "staggerMs" INTEGER NOT NULL DEFAULT 200,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "channelId" INTEGER,
    CONSTRAINT "EventSession_channelId_fkey" FOREIGN KEY ("channelId") REFERENCES "Channel" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_EventSession" ("channelId", "createdAt", "id", "isActive", "name", "regexFilter", "updatedAt") SELECT "channelId", "createdAt", "id", "isActive", "name", "regexFilter", "updatedAt" FROM "EventSession";
DROP TABLE "EventSession";
ALTER TABLE "new_EventSession" RENAME TO "EventSession";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

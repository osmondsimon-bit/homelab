// Stores category-only snapshots and validated memos in the VM-local SQLite audit database.
import { chmodSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

export class MemoStore {
  constructor(path) {
    mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
    this.database = new DatabaseSync(path, { timeout: 5000 });
    chmodSync(path, 0o600);
    this.database.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA foreign_keys = ON;
      CREATE TABLE IF NOT EXISTS memos (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL DEFAULT 'monthly',
        month TEXT NOT NULL,
        created_at TEXT NOT NULL,
        snapshot_hash TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        memo_json TEXT NOT NULL,
        model TEXT NOT NULL,
        response_id TEXT NOT NULL,
        usage_json TEXT
      ) STRICT;
      CREATE INDEX IF NOT EXISTS memos_month_created
        ON memos(month, created_at DESC);
    `);
    const memoColumns = this.database.prepare('PRAGMA table_info(memos)').all();
    if (!memoColumns.some(column => column.name === 'kind')) {
      this.database.exec("ALTER TABLE memos ADD COLUMN kind TEXT NOT NULL DEFAULT 'monthly'");
    }
    this.insert = this.database.prepare(`
      INSERT INTO memos (
        kind, month, created_at, snapshot_hash, payload_json, memo_json,
        model, response_id, usage_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    this.selectRecent = this.database.prepare(`
      SELECT id, kind, month, created_at, snapshot_hash, payload_json, memo_json,
             model, response_id, usage_json
      FROM memos
      ORDER BY created_at DESC, id DESC
      LIMIT ?
    `);
  }

  save({ kind = 'monthly', month, snapshotHash, payload, memo, model, responseId, usage }) {
    if (!['monthly', 'long_term'].includes(kind)) {
      throw new Error('unsupported memo kind');
    }
    const result = this.insert.run(
      kind,
      month,
      new Date().toISOString(),
      snapshotHash,
      JSON.stringify(payload),
      JSON.stringify(memo),
      model,
      responseId,
      usage === null ? null : JSON.stringify(usage),
    );
    return Number(result.lastInsertRowid);
  }

  list(limit = 24) {
    return this.selectRecent.all(limit).map(row => {
      const payload = JSON.parse(row.payload_json);
      const memo = JSON.parse(row.memo_json);
      return {
        id: row.id,
        kind: row.kind,
        month: row.month,
        createdAt: row.created_at,
        snapshotHash: row.snapshot_hash,
        payload,
        memo,
        headline: memo.headline,
        summary: memo.summary,
        model: row.model,
        responseId: row.response_id,
        usage: row.usage_json === null ? null : JSON.parse(row.usage_json),
      };
    });
  }

  close() {
    this.database.close();
  }
}

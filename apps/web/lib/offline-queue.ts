import type { ScanPayload, ScanResult } from "@/types/api";

/**
 * Scans taken without a working network are kept in IndexedDB until they can be synced.
 * Only the scan payload (QR text, GPS fix, phone clock, device id) is stored: no tokens,
 * no passwords. The server still decides whether each scan counts.
 */
const DB_NAME = "attendance-offline";
const PENDING = "pending";
const OUTCOMES = "outcomes";

export interface PendingScan {
  client_uuid: string;
  payload: ScanPayload;
  queued_at: string;
}

export interface StoredOutcome {
  client_uuid: string;
  result: ScanResult;
  at: string;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(PENDING)) db.createObjectStore(PENDING, { keyPath: "client_uuid" });
      if (!db.objectStoreNames.contains(OUTCOMES)) db.createObjectStore(OUTCOMES, { keyPath: "client_uuid" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(store: string, mode: IDBTransactionMode, run: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const t = db.transaction(store, mode);
      const req = run(t.objectStore(store));
      t.oncomplete = () => resolve(req.result);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
  } finally {
    db.close();
  }
}

export const queue = {
  async add(payload: ScanPayload): Promise<void> {
    const item: PendingScan = { client_uuid: payload.client_uuid, payload, queued_at: new Date().toISOString() };
    await tx(PENDING, "readwrite", (s) => s.put(item));
  },
  async list(): Promise<PendingScan[]> {
    const all = await tx<PendingScan[]>(PENDING, "readonly", (s) => s.getAll());
    return all.sort((a, b) => a.queued_at.localeCompare(b.queued_at));
  },
  async remove(clientUuid: string): Promise<void> {
    await tx(PENDING, "readwrite", (s) => s.delete(clientUuid));
  },
  async count(): Promise<number> {
    return tx(PENDING, "readonly", (s) => s.count());
  },
  async saveOutcome(result: ScanResult): Promise<void> {
    const item: StoredOutcome = { client_uuid: result.client_uuid, result, at: new Date().toISOString() };
    await tx(OUTCOMES, "readwrite", (s) => s.put(item));
  },
  async outcomes(): Promise<StoredOutcome[]> {
    const all = await tx<StoredOutcome[]>(OUTCOMES, "readonly", (s) => s.getAll());
    return all.sort((a, b) => b.at.localeCompare(a.at)).slice(0, 20);
  },
};

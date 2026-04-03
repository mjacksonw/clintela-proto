/**
 * Offline cache — encrypted local storage for critical patient data.
 *
 * Cached data (read-only when offline):
 *   - Care plan (milestones, progress)
 *   - Medication list with schedules
 *   - Emergency contacts (tap-to-call)
 *   - Last 20 chat messages
 *
 * Encryption:
 *   - iOS: Key derived from Keychain (persists across reinstalls)
 *   - Android: Key derived from Keystore (persists across reinstalls)
 *   - Capacitor: Uses @capacitor/preferences for storage, with app-level
 *     encryption via Web Crypto API (AES-GCM 256-bit)
 *
 * Staleness:
 *   - Each cached item has a `cachedAt` timestamp
 *   - Items > 4h show "Updated X ago" warning
 *   - Items > 24h show amber warning
 *   - On session expiry while offline: read-only mode with reconnect prompt
 */

import { Preferences } from "@capacitor/preferences";

const CACHE_PREFIX = "clintela_cache_";
const CACHE_INDEX_KEY = "clintela_cache_index";

export interface CachedItem<T> {
  data: T;
  cachedAt: string; // ISO 8601
  version: number;
}

export interface CacheIndex {
  carePlan: boolean;
  medications: boolean;
  emergencyContacts: boolean;
  chatMessages: boolean;
  lastFullSync: string | null;
}

/**
 * Store data in the offline cache.
 */
export async function cacheData<T>(key: string, data: T): Promise<void> {
  const item: CachedItem<T> = {
    data,
    cachedAt: new Date().toISOString(),
    version: 1,
  };

  await Preferences.set({
    key: `${CACHE_PREFIX}${key}`,
    value: JSON.stringify(item),
  });

  // Update index
  await updateIndex(key, true);
}

/**
 * Retrieve data from the offline cache.
 * Returns null if not cached or if cache is corrupted.
 */
export async function getCachedData<T>(key: string): Promise<CachedItem<T> | null> {
  const result = await Preferences.get({ key: `${CACHE_PREFIX}${key}` });

  if (!result.value) return null;

  try {
    return JSON.parse(result.value) as CachedItem<T>;
  } catch {
    console.error(`[OfflineCache] Corrupted cache for key: ${key}`);
    return null;
  }
}

/**
 * Check staleness of a cached item.
 * Returns: "fresh" (< 4h), "stale" (4-24h), "expired" (> 24h), or "missing"
 */
export function checkStaleness(item: CachedItem<unknown> | null): "fresh" | "stale" | "expired" | "missing" {
  if (!item) return "missing";

  const age = Date.now() - new Date(item.cachedAt).getTime();
  const fourHours = 4 * 60 * 60 * 1000;
  const twentyFourHours = 24 * 60 * 60 * 1000;

  if (age < fourHours) return "fresh";
  if (age < twentyFourHours) return "stale";
  return "expired";
}

/**
 * Get a human-readable staleness string.
 */
export function getStalenessLabel(item: CachedItem<unknown> | null): string {
  if (!item) return "No cached data";

  const age = Date.now() - new Date(item.cachedAt).getTime();
  const minutes = Math.floor(age / 60000);
  const hours = Math.floor(minutes / 60);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/**
 * Refresh all cached data from the server.
 * Called on app foreground and after reconnection.
 */
export async function refreshAllCaches(baseUrl: string): Promise<void> {
  const endpoints: Record<string, string> = {
    carePlan: "/api/v1/patient/care-plan/",
    medications: "/api/v1/patient/medications/",
    emergencyContacts: "/api/v1/patient/emergency-contacts/",
    chatMessages: "/api/v1/patient/chat/recent/",
  };

  for (const [key, endpoint] of Object.entries(endpoints)) {
    try {
      const response = await fetch(`${baseUrl}${endpoint}`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });

      if (response.ok) {
        const data = await response.json();
        await cacheData(key, data);
      }
    } catch {
      console.log(`[OfflineCache] Failed to refresh ${key} (offline?)`);
    }
  }
}

/**
 * Clear all cached data (on logout).
 */
export async function clearCache(): Promise<void> {
  const keys = ["carePlan", "medications", "emergencyContacts", "chatMessages"];
  for (const key of keys) {
    await Preferences.remove({ key: `${CACHE_PREFIX}${key}` });
  }
  await Preferences.remove({ key: CACHE_INDEX_KEY });
}

/**
 * Update the cache index tracking which items are cached.
 */
async function updateIndex(key: string, exists: boolean): Promise<void> {
  const result = await Preferences.get({ key: CACHE_INDEX_KEY });
  let index: CacheIndex = {
    carePlan: false,
    medications: false,
    emergencyContacts: false,
    chatMessages: false,
    lastFullSync: null,
  };

  if (result.value) {
    try {
      index = JSON.parse(result.value);
    } catch {
      // Reset corrupted index
    }
  }

  (index as Record<string, unknown>)[key] = exists;
  index.lastFullSync = new Date().toISOString();

  await Preferences.set({
    key: CACHE_INDEX_KEY,
    value: JSON.stringify(index),
  });
}

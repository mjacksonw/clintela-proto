/**
 * Health data sync service — syncs HealthKit / Health Connect data to the backend.
 *
 * Architecture:
 *   - iOS: HealthKit via HKAnchoredObjectQuery (anchor-based incremental sync)
 *   - Android: Health Connect via readRecords (time-range based)
 *   - Both: batch POST to /api/v1/health/sync/ (max 500 per request)
 *
 * Sync triggers:
 *   1. App foreground (always sync)
 *   2. Background fetch (BGAppRefreshTask, advisory 4h interval)
 *   3. Manual pull-to-refresh on health dashboard
 *
 * OMOP Concept ID mappings (must match apps/clinical/constants.py):
 *   Heart Rate: 3027018
 *   Systolic BP: 3004249
 *   Diastolic BP: 3012888
 *   Body Weight: 3025315
 *   SpO2: 3016502
 *   Temperature: 3020891
 *   Daily Steps: 40762499
 *   Sleep Duration: 40762503
 */

const HEALTH_SYNC_ENDPOINT = "/api/v1/health/sync/";
const MAX_BATCH_SIZE = 500;

// Anchor storage key for HealthKit incremental sync
const ANCHOR_STORAGE_KEY = "clintela_healthkit_anchor";

/** OMOP Concept IDs mapped from HealthKit/Health Connect data types */
export const CONCEPT_MAP: Record<string, number> = {
  // HealthKit type identifiers
  "HKQuantityTypeIdentifierHeartRate": 3027018,
  "HKQuantityTypeIdentifierBloodPressureSystolic": 3004249,
  "HKQuantityTypeIdentifierBloodPressureDiastolic": 3012888,
  "HKQuantityTypeIdentifierBodyMass": 3025315,
  "HKQuantityTypeIdentifierOxygenSaturation": 3016502,
  "HKQuantityTypeIdentifierBodyTemperature": 3020891,
  "HKQuantityTypeIdentifierStepCount": 40762499,
  "HKCategoryTypeIdentifierSleepAnalysis": 40762503,

  // Health Connect data types
  "HeartRate": 3027018,
  "BloodPressure.systolic": 3004249,
  "BloodPressure.diastolic": 3012888,
  "Weight": 3025315,
  "OxygenSaturation": 3016502,
  "BodyTemperature": 3020891,
  "Steps": 40762499,
  "SleepSession": 40762503,
};

export interface HealthObservation {
  concept_id: number;
  value_numeric: number | null;
  value_text: string;
  unit: string;
  observed_at: string; // ISO 8601
  source_device: string;
  metadata: Record<string, unknown> | null;
}

export interface SyncResult {
  received: number;
  processed: number;
  skipped: number;
  errors: string[];
}

/**
 * Sync health observations to the backend.
 * Automatically paginates into batches of 500.
 */
export async function syncHealthData(
  baseUrl: string,
  source: "healthkit" | "health_connect",
  observations: HealthObservation[],
): Promise<SyncResult> {
  if (observations.length === 0) {
    return { received: 0, processed: 0, skipped: 0, errors: [] };
  }

  const totals: SyncResult = { received: 0, processed: 0, skipped: 0, errors: [] };

  // Paginate into batches of MAX_BATCH_SIZE
  for (let i = 0; i < observations.length; i += MAX_BATCH_SIZE) {
    const batch = observations.slice(i, i + MAX_BATCH_SIZE);
    const result = await syncBatch(baseUrl, source, batch);
    totals.received += result.received;
    totals.processed += result.processed;
    totals.skipped += result.skipped;
    totals.errors.push(...result.errors);
  }

  console.log(
    `[HealthSync] Complete: ${totals.processed}/${totals.received} processed, ${totals.skipped} skipped`,
  );

  return totals;
}

/**
 * Sync a single batch (max 500 observations).
 */
async function syncBatch(
  baseUrl: string,
  source: string,
  observations: HealthObservation[],
): Promise<SyncResult> {
  try {
    const response = await fetch(`${baseUrl}${HEALTH_SYNC_ENDPOINT}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, observations }),
    });

    if (response.ok) {
      return await response.json();
    }

    console.error("[HealthSync] Batch sync failed:", response.status);
    return {
      received: observations.length,
      processed: 0,
      skipped: observations.length,
      errors: [`HTTP ${response.status}`],
    };
  } catch (error) {
    console.error("[HealthSync] Batch sync error:", error);
    return {
      received: observations.length,
      processed: 0,
      skipped: observations.length,
      errors: [String(error)],
    };
  }
}

/**
 * Get the stored HealthKit anchor for incremental sync.
 * Returns null on first sync (full historical pull).
 */
export function getStoredAnchor(): string | null {
  try {
    return localStorage.getItem(ANCHOR_STORAGE_KEY);
  } catch {
    return null;
  }
}

/**
 * Store the HealthKit anchor after a successful sync.
 */
export function storeAnchor(anchor: string): void {
  try {
    localStorage.setItem(ANCHOR_STORAGE_KEY, anchor);
  } catch {
    console.error("[HealthSync] Failed to store anchor");
  }
}

/**
 * Map a HealthKit/Health Connect data type to an OMOP concept ID.
 * Returns null if the type is not supported.
 */
export function mapToConcept(dataType: string): number | null {
  return CONCEPT_MAP[dataType] ?? null;
}

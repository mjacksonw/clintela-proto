/**
 * WebView-to-native event bridge — listens for events from the Django WebView
 * and propagates them to native components (widget, offline cache, analytics).
 *
 * Events are dispatched from Django templates via:
 *   window.dispatchEvent(new CustomEvent("clintela:checkin_completed", { detail: {...} }))
 *
 * Native listeners update:
 *   - Home screen widget data (via App Groups / SharedPreferences)
 *   - Offline cache (refresh relevant section)
 *   - Analytics events
 */

import { refreshAllCaches, cacheData } from "./offline-cache";

export type BridgeEventType =
  | "checkin_completed"
  | "message_read"
  | "survey_submitted"
  | "care_plan_viewed"
  | "medication_taken"
  | "session_expired";

export interface BridgeEvent<T = unknown> {
  type: BridgeEventType;
  detail: T;
  timestamp: string;
}

interface CheckinDetail {
  surveyId: string;
  completedAt: string;
}

interface MessageDetail {
  messageId: string;
  conversationId: string;
}

interface SurveyDetail {
  surveyId: string;
  score?: number;
}

interface CarePlanDetail {
  milestoneId?: string;
}

interface MedicationDetail {
  medicationName: string;
  takenAt: string;
}

type EventHandler = (detail: unknown) => void | Promise<void>;

const listeners: Map<BridgeEventType, EventHandler[]> = new Map();
let baseUrl = "";

/**
 * Initialize the event bridge. Call once on app startup.
 * Registers window event listeners for all bridge events.
 */
export function initializeEventBridge(serverBaseUrl: string): void {
  baseUrl = serverBaseUrl;

  const eventTypes: BridgeEventType[] = [
    "checkin_completed",
    "message_read",
    "survey_submitted",
    "care_plan_viewed",
    "medication_taken",
    "session_expired",
  ];

  for (const eventType of eventTypes) {
    window.addEventListener(`clintela:${eventType}`, ((event: CustomEvent) => {
      handleBridgeEvent(eventType, event.detail);
    }) as EventListener);
  }

  // Register default handlers
  onBridgeEvent("checkin_completed", handleCheckinCompleted);
  onBridgeEvent("message_read", handleMessageRead);
  onBridgeEvent("care_plan_viewed", handleCarePlanViewed);
  onBridgeEvent("medication_taken", handleMedicationTaken);
  onBridgeEvent("session_expired", handleSessionExpired);

  console.log("[EventBridge] Initialized with", eventTypes.length, "event types");
}

/**
 * Register a handler for a bridge event type.
 */
export function onBridgeEvent(type: BridgeEventType, handler: EventHandler): void {
  if (!listeners.has(type)) {
    listeners.set(type, []);
  }
  listeners.get(type)!.push(handler);
}

/**
 * Dispatch a bridge event from native code to the WebView.
 * Useful for native → web communication (e.g., widget tap → navigate).
 */
export function dispatchToWebView(type: BridgeEventType, detail: unknown): void {
  window.dispatchEvent(
    new CustomEvent(`clintela:${type}`, { detail }),
  );
}

// ─── Internal ──────────────────────────────────────────────────────

function handleBridgeEvent(type: BridgeEventType, detail: unknown): void {
  console.log(`[EventBridge] ${type}`, detail);

  const handlers = listeners.get(type) || [];
  for (const handler of handlers) {
    try {
      handler(detail);
    } catch (error) {
      console.error(`[EventBridge] Handler error for ${type}:`, error);
    }
  }
}

async function handleCheckinCompleted(detail: unknown): Promise<void> {
  const { completedAt } = detail as CheckinDetail;
  // Update widget data: last check-in timestamp
  await updateWidgetData({ lastCheckinAt: completedAt });
  // Refresh care plan cache (milestones may have progressed)
  await refreshAllCaches(baseUrl);
}

async function handleMessageRead(_detail: unknown): Promise<void> {
  // Refresh chat cache to keep offline messages current
  try {
    const response = await fetch(`${baseUrl}/api/v1/patient/chat/recent/`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (response.ok) {
      const data = await response.json();
      await cacheData("chatMessages", data);
    }
  } catch {
    // Offline, skip
  }
}

async function handleCarePlanViewed(_detail: unknown): Promise<void> {
  // Refresh care plan cache
  try {
    const response = await fetch(`${baseUrl}/api/v1/patient/care-plan/`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (response.ok) {
      const data = await response.json();
      await cacheData("carePlan", data);
    }
  } catch {
    // Offline, skip
  }
}

async function handleMedicationTaken(detail: unknown): Promise<void> {
  const { medicationName, takenAt } = detail as MedicationDetail;
  await updateWidgetData({ lastMedicationAt: takenAt, lastMedicationName: medicationName });
}

function handleSessionExpired(_detail: unknown): void {
  // Import AuthBridge and clear cache
  import("../plugins/auth-bridge").then(({ clearAuthCache }) => {
    clearAuthCache();
  });
}

/**
 * Update the shared widget data store.
 * iOS: App Groups UserDefaults
 * Android: SharedPreferences
 */
async function updateWidgetData(data: Record<string, unknown>): Promise<void> {
  try {
    const { Preferences } = await import("@capacitor/preferences");
    const existing = await Preferences.get({ key: "clintela_widget_data" });
    let widgetData: Record<string, unknown> = {};

    if (existing.value) {
      try {
        widgetData = JSON.parse(existing.value);
      } catch {
        // Reset corrupted data
      }
    }

    Object.assign(widgetData, data, { updatedAt: new Date().toISOString() });

    await Preferences.set({
      key: "clintela_widget_data",
      value: JSON.stringify(widgetData),
    });
  } catch (error) {
    console.error("[EventBridge] Widget data update failed:", error);
  }
}

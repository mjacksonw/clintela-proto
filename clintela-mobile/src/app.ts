/**
 * Clintela Mobile — main entry point.
 *
 * Capacitor hybrid app: WebView wrapping Django patient interface + native
 * screens for onboarding, health permissions, and voice input.
 *
 * Boot sequence:
 *   1. Splash screen (native, Satoshi wordmark + teal line draw, 0.8s)
 *   2. Check auth status via AuthBridge
 *   3. If authenticated → initialize services → hide splash → show WebView
 *   4. If not authenticated → show native onboarding
 *   5. On foreground resume → refresh caches, sync health data
 */

import { App } from "@capacitor/app";
import { SplashScreen } from "@capacitor/splash-screen";

import { getAuthStatus, isSessionExpiringSoon } from "./plugins/auth-bridge";
import { initializeEventBridge } from "./services/event-bridge";
import { syncHealthData, type HealthObservation } from "./services/health-sync";
import { refreshAllCaches } from "./services/offline-cache";
import { initializePush } from "./services/push-notifications";

// ─── Configuration ────────────────────────────────────────────────

const BASE_URL = getBaseUrl();

function getBaseUrl(): string {
  // In production, webDir is bundled. Server URL comes from capacitor.config.ts
  // In dev, override via environment or config
  return (window as Record<string, unknown>).__CLINTELA_BASE_URL as string ?? "";
}

// ─── Boot Sequence ────────────────────────────────────────────────

async function boot(): Promise<void> {
  console.log("[App] Booting Clintela Mobile...");

  // Step 1: Check auth
  const auth = await getAuthStatus(BASE_URL);

  if (!auth.authenticated) {
    console.log("[App] Not authenticated, showing onboarding");
    await SplashScreen.hide();
    showOnboarding();
    return;
  }

  console.log("[App] Authenticated as:", auth.preferredName ?? auth.patientId);

  // Step 2: Initialize services in parallel
  await Promise.allSettled([
    initializePush({
      baseUrl: BASE_URL,
      onNotificationReceived: handleForegroundNotification,
      onNotificationAction: handleNotificationTap,
    }),
    refreshAllCaches(BASE_URL),
    initializeEventBridge(BASE_URL),
  ]);

  // Step 3: Hide splash and show WebView content
  await SplashScreen.hide({ fadeOutDuration: 200 });

  // Step 4: Trigger initial health sync
  triggerHealthSync();

  console.log("[App] Boot complete");
}

// ─── Lifecycle Handlers ──────────────────────────────────────────

App.addListener("appStateChange", async ({ isActive }) => {
  if (isActive) {
    console.log("[App] Resumed to foreground");

    // Check auth on resume
    const auth = await getAuthStatus(BASE_URL, true);
    if (!auth.authenticated) {
      showReauthPrompt();
      return;
    }

    // Check for expiring session
    if (isSessionExpiringSoon()) {
      console.log("[App] Session expiring soon, proactive re-auth");
    }

    // Refresh caches and sync health data
    await refreshAllCaches(BASE_URL);
    triggerHealthSync();
  }
});

App.addListener("appUrlOpen", (data) => {
  console.log("[App] URL opened:", data.url);
  handleDeepLink(data.url);
});

// ─── Push Notification Handlers ──────────────────────────────────

function handleForegroundNotification(notification: { data?: Record<string, string> }): void {
  // In foreground, we rely on the in-app WebSocket notification UI.
  // Push is suppressed by the routing hierarchy when WS is active.
  // If we get here, it means the push arrived before WS connected.
  console.log("[App] Foreground notification (unexpected):", notification.data);
}

function handleNotificationTap(action: { notification: { data?: Record<string, string> } }): void {
  const data = action.notification.data;
  if (!data) return;

  // Deep link based on notification type
  const type = data.type;
  switch (type) {
    case "reminder":
      navigateTo("/patient/check-in/");
      break;
    case "escalation":
    case "update":
      navigateTo("/patient/messages/");
      break;
    case "alert":
      navigateTo("/patient/health/");
      break;
    default:
      navigateTo("/patient/");
  }
}

// ─── Health Sync ─────────────────────────────────────────────────

function triggerHealthSync(): void {
  // Health data collection is handled by native HealthKit/Health Connect plugins.
  // This stub is called on foreground to trigger the sync pipeline.
  // In a full implementation, the native plugin provides observations via a
  // Capacitor bridge event, which we forward to syncHealthData().
  console.log("[App] Health sync triggered (native plugin will provide data)");

  // Listen for health data from native plugin
  window.addEventListener("clintela:health_data_ready", async (event) => {
    const { source, observations } = (event as CustomEvent).detail as {
      source: "healthkit" | "health_connect";
      observations: HealthObservation[];
    };
    const result = await syncHealthData(BASE_URL, source, observations);
    console.log("[App] Health sync result:", result);
  });
}

// ─── Navigation ──────────────────────────────────────────────────

function navigateTo(path: string): void {
  // Navigate the WebView to a specific path
  window.location.href = path;
}

function handleDeepLink(url: string): void {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname;

    // Route deep links to WebView paths
    if (path.startsWith("/patient/")) {
      navigateTo(path);
    }
  } catch {
    console.error("[App] Invalid deep link:", url);
  }
}

// ─── Onboarding / Re-auth ────────────────────────────────────────

function showOnboarding(): void {
  // In a full implementation, this triggers the native SwiftUI/Jetpack Compose
  // onboarding flow via a Capacitor plugin. For now, redirect to web auth.
  console.log("[App] Showing onboarding flow");
  navigateTo("/patient/");
}

function showReauthPrompt(): void {
  // Session expired — redirect to magic link auth
  console.log("[App] Session expired, redirecting to auth");
  navigateTo("/accounts/start/");
}

// ─── Start ───────────────────────────────────────────────────────

boot().catch((error) => {
  console.error("[App] Boot failed:", error);
  SplashScreen.hide();
});

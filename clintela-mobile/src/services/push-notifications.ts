/**
 * Push notification service — registers device tokens and handles incoming pushes.
 *
 * Flow:
 *   1. App launch → request permission → receive FCM token
 *   2. Register token with Django backend (POST /api/v1/devices/register/)
 *   3. On push received → route to appropriate screen via deep link
 *   4. On token refresh → re-register with backend
 *   5. On logout → deactivate token (DELETE /api/v1/devices/{token}/)
 */

import { Capacitor } from "@capacitor/core";
import { PushNotifications } from "@capacitor/push-notifications";
import type { ActionPerformed, PushNotificationSchema, Token } from "@capacitor/push-notifications";

const DEVICE_REGISTER_ENDPOINT = "/api/v1/devices/register/";
const DEVICE_DELETE_ENDPOINT = "/api/v1/devices/"; // + {token}/

let currentToken: string | null = null;

export interface PushConfig {
  baseUrl: string;
  onNotificationReceived?: (notification: PushNotificationSchema) => void;
  onNotificationAction?: (action: ActionPerformed) => void;
}

/**
 * Initialize push notifications. Call once on app startup after auth is confirmed.
 */
export async function initializePush(config: PushConfig): Promise<void> {
  if (!Capacitor.isNativePlatform()) {
    console.log("[Push] Not a native platform, skipping initialization");
    return;
  }

  // Check and request permission
  let permStatus = await PushNotifications.checkPermissions();

  if (permStatus.receive === "prompt") {
    permStatus = await PushNotifications.requestPermissions();
  }

  if (permStatus.receive !== "granted") {
    console.log("[Push] Permission not granted:", permStatus.receive);
    return;
  }

  // Register listeners before calling register()
  PushNotifications.addListener("registration", async (token: Token) => {
    console.log("[Push] Token received:", token.value.substring(0, 8) + "...");
    currentToken = token.value;
    await registerTokenWithBackend(config.baseUrl, token.value);
  });

  PushNotifications.addListener("registrationError", (error) => {
    console.error("[Push] Registration error:", error);
  });

  PushNotifications.addListener(
    "pushNotificationReceived",
    (notification: PushNotificationSchema) => {
      console.log("[Push] Notification received in foreground:", notification.id);
      config.onNotificationReceived?.(notification);
    },
  );

  PushNotifications.addListener(
    "pushNotificationActionPerformed",
    (action: ActionPerformed) => {
      console.log("[Push] Notification action:", action.actionId);
      config.onNotificationAction?.(action);
    },
  );

  // Trigger registration
  await PushNotifications.register();
}

/**
 * Register the FCM token with the Django backend.
 */
async function registerTokenWithBackend(baseUrl: string, token: string): Promise<void> {
  const platform = Capacitor.getPlatform(); // "ios" or "android"

  try {
    const response = await fetch(`${baseUrl}${DEVICE_REGISTER_ENDPOINT}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        platform,
        device_name: await getDeviceName(),
      }),
    });

    if (response.ok) {
      const data = await response.json();
      console.log("[Push] Token registered:", data.created ? "new" : "re-activated");
    } else {
      console.error("[Push] Token registration failed:", response.status);
    }
  } catch (error) {
    console.error("[Push] Token registration error:", error);
  }
}

/**
 * Deactivate the current push token (on logout or uninstall).
 */
export async function deactivateToken(baseUrl: string): Promise<void> {
  if (!currentToken) return;

  try {
    await fetch(`${baseUrl}${DEVICE_DELETE_ENDPOINT}${currentToken}/`, {
      method: "DELETE",
      credentials: "include",
    });
    console.log("[Push] Token deactivated");
    currentToken = null;
  } catch (error) {
    console.error("[Push] Token deactivation error:", error);
  }
}

/**
 * Get a human-readable device name.
 */
async function getDeviceName(): Promise<string> {
  try {
    const { Device } = await import("@capacitor/device");
    const info = await Device.getInfo();
    return `${info.manufacturer} ${info.model}`;
  } catch {
    return Capacitor.getPlatform() === "ios" ? "iPhone" : "Android";
  }
}

/**
 * Get the current push token (for debugging).
 */
export function getCurrentToken(): string | null {
  return currentToken;
}

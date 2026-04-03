/**
 * AuthBridge — manages authentication state between WebView and native screens.
 *
 * The patient auth flow uses magic link + DOB verification, which sets session
 * cookies in the WebView. Native screens need to validate this session before
 * making API calls. If the session is expired/missing, redirect to WebView re-auth.
 *
 * Flow:
 *   1. WebView loads magic link → Django sets session cookie
 *   2. AuthBridge extracts session validity from a lightweight /api/v1/auth/status endpoint
 *   3. Native screens call AuthBridge.isAuthenticated() before transitions
 *   4. On expiry: redirect to WebView magic link re-auth
 */

export interface AuthStatus {
  authenticated: boolean;
  patientId: string | null;
  expiresAt: string | null;
  preferredName: string | null;
}

const AUTH_STATUS_ENDPOINT = "/api/v1/auth/status/";
const AUTH_CACHE_KEY = "clintela_auth_status";
const AUTH_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

let cachedStatus: AuthStatus | null = null;
let cacheTimestamp = 0;

/**
 * Check if the current session is valid.
 * Uses a lightweight API call with cookie-based auth.
 * Results are cached for 5 minutes to avoid excessive network calls.
 */
export async function isAuthenticated(baseUrl: string): Promise<boolean> {
  const status = await getAuthStatus(baseUrl);
  return status.authenticated;
}

/**
 * Get full auth status including patient info.
 * Cached for 5 minutes. Force refresh with `forceRefresh: true`.
 */
export async function getAuthStatus(
  baseUrl: string,
  forceRefresh = false,
): Promise<AuthStatus> {
  const now = Date.now();

  // Return cached status if fresh
  if (!forceRefresh && cachedStatus && now - cacheTimestamp < AUTH_CACHE_TTL_MS) {
    return cachedStatus;
  }

  try {
    const response = await fetch(`${baseUrl}${AUTH_STATUS_ENDPOINT}`, {
      credentials: "include", // Send cookies
      headers: { Accept: "application/json" },
    });

    if (response.ok) {
      const data = await response.json();
      cachedStatus = {
        authenticated: data.authenticated ?? false,
        patientId: data.patient_id ?? null,
        expiresAt: data.expires_at ?? null,
        preferredName: data.preferred_name ?? null,
      };
    } else {
      cachedStatus = {
        authenticated: false,
        patientId: null,
        expiresAt: null,
        preferredName: null,
      };
    }
  } catch {
    // Network error — return cached if available, otherwise unauthenticated
    if (cachedStatus) {
      return cachedStatus;
    }
    cachedStatus = {
      authenticated: false,
      patientId: null,
      expiresAt: null,
      preferredName: null,
    };
  }

  cacheTimestamp = now;
  return cachedStatus;
}

/**
 * Clear cached auth status (e.g., on logout or session expiry detection).
 */
export function clearAuthCache(): void {
  cachedStatus = null;
  cacheTimestamp = 0;
}

/**
 * Check if the session is about to expire (within 5 minutes).
 * Useful for proactive re-auth prompts.
 */
export function isSessionExpiringSoon(): boolean {
  if (!cachedStatus?.expiresAt) return false;
  const expiresAt = new Date(cachedStatus.expiresAt).getTime();
  const fiveMinutes = 5 * 60 * 1000;
  return expiresAt - Date.now() < fiveMinutes;
}

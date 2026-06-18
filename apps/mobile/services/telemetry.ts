import { ApplicationInsights, SeverityLevel } from '@microsoft/applicationinsights-web';
import { ReactNativePlugin } from '@microsoft/applicationinsights-react-native';

const RNPlugin = new ReactNativePlugin();

const connectionString =
  process.env.EXPO_PUBLIC_APPINSIGHTS_CONNECTION_STRING ?? '';

export const appInsights = new ApplicationInsights({
  config: {
    connectionString,
    extensions: [RNPlugin],
    disableFetchTracking: false, // Track fetch() calls as dependencies
    enableAutoRouteTracking: false, // We handle navigation tracking ourselves
    disableExceptionTracking: false, // Track unhandled JS exceptions
    maxBatchInterval: 15000, // Batch telemetry every 15 s to reduce noise
    disableTelemetry: !connectionString,
  },
});

if (connectionString) {
  appInsights.loadAppInsights();
}

// ---------------------------------------------------------------------------
// User & session context
// ---------------------------------------------------------------------------

/** Set authenticated user context after sign-in. */
export function setUserContext(userId: string, householdId?: string) {
  if (!connectionString) return;
  appInsights.setAuthenticatedUserContext(userId, householdId, true);
}

/** Clear user context on sign-out. */
export function clearUserContext() {
  if (!connectionString) return;
  appInsights.clearAuthenticatedUserContext();
}

// ---------------------------------------------------------------------------
// Screen / navigation tracking
// ---------------------------------------------------------------------------

/** Track a screen view (maps to pageView in App Insights). */
export function trackScreenView(
  screenName: string,
  properties?: Record<string, string>,
) {
  if (!connectionString) return;
  appInsights.trackPageView({ name: screenName, properties });
}

// ---------------------------------------------------------------------------
// Custom events & traces
// ---------------------------------------------------------------------------

/** Track a custom business event (e.g. "expense_confirmed"). */
export function trackEvent(
  name: string,
  properties?: Record<string, string>,
) {
  if (!connectionString) return;
  appInsights.trackEvent({ name }, properties);
}

/** Track a warning-level trace. */
export function trackWarning(
  message: string,
  properties?: Record<string, string>,
) {
  if (!connectionString) return;
  appInsights.trackTrace(
    { message, severityLevel: SeverityLevel.Warning },
    properties,
  );
}

// ---------------------------------------------------------------------------
// Exception tracking
// ---------------------------------------------------------------------------

/** Track an Error instance with optional custom properties. */
export function trackException(
  error: Error,
  properties?: Record<string, string>,
) {
  if (!connectionString) return;
  appInsights.trackException(
    { exception: error, severityLevel: SeverityLevel.Error },
    properties,
  );
}

/** Track an API call failure as an exception with structured properties. */
export function trackApiError(
  method: string,
  path: string,
  status: number,
  detail: string,
) {
  if (!connectionString) return;
  appInsights.trackException(
    {
      exception: new Error(`API ${method} ${path}: ${status} – ${detail}`),
      severityLevel: status >= 500 ? SeverityLevel.Error : SeverityLevel.Warning,
    },
    { method, path, status: String(status), detail },
  );
}
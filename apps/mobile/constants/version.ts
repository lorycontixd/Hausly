import Constants from "expo-constants";

/**
 * App version read from app.json (single source of truth for mobile versioning).
 * Access via Constants so the value is never hardcoded in application code.
 */
export const APP_VERSION: string = Constants.expoConfig?.version ?? "0.0.0";

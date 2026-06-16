export const colors = {
  // Brand
  primary: "#6366F1",
  primaryLight: "#A5B4FC",
  primaryDark: "#4338CA",
  primarySoft: "#EEF2FF",
  secondary: "#10B981",
  secondaryLight: "#6EE7B7",
  destructive: "#EF4444",
  destructiveLight: "#FEE2E2",

  // Surfaces
  background: "#F8FAFC",
  surface: "#FFFFFF",
  surfaceElevated: "#FFFFFF",
  border: "#E2E8F0",
  borderLight: "#F1F5F9",

  // Text
  text: "#1E293B",
  textSecondary: "#64748B",
  textTertiary: "#94A3B8",
  textInverse: "#FFFFFF",

  // Semantic
  success: "#10B981",
  warning: "#F59E0B",
  error: "#EF4444",
  info: "#3B82F6",

  // Module accent colors
  module: {
    grocery: "#10B981",
    grocerySoft: "#ECFDF5",
    expense: "#F59E0B",
    expenseSoft: "#FFFBEB",
    meal: "#EC4899",
    mealSoft: "#FDF2F8",
    chore: "#8B5CF6",
    choreSoft: "#F5F3FF",
  },
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
} as const;

export const borderRadius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  full: 9999,
} as const;

export const shadows = {
  sm: {
    shadowColor: "#1E293B",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  md: {
    shadowColor: "#1E293B",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.06,
    shadowRadius: 12,
    elevation: 3,
  },
  lg: {
    shadowColor: "#1E293B",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 24,
    elevation: 5,
  },
} as const;

export const typography = {
  heading: {
    fontSize: 24,
    fontWeight: "700" as const,
    lineHeight: 32,
    letterSpacing: -0.3,
  },
  subheading: {
    fontSize: 18,
    fontWeight: "600" as const,
    lineHeight: 24,
    letterSpacing: -0.2,
  },
  body: {
    fontSize: 16,
    fontWeight: "400" as const,
    lineHeight: 24,
  },
  bodySmall: {
    fontSize: 14,
    fontWeight: "400" as const,
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    fontWeight: "500" as const,
    lineHeight: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: "600" as const,
    lineHeight: 20,
  },
} as const;

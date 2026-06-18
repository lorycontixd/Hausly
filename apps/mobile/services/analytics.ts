import analytics from '@react-native-firebase/analytics';
import crashlytics from '@react-native-firebase/crashlytics';

// ---------------------------------------------------------------------------
// Crashlytics setup
// ---------------------------------------------------------------------------

/** Set user identity for crash grouping */
export function setCrashUser(userId: string, householdId?: string) {
  crashlytics().setUserId(userId);
  if (householdId) {
    crashlytics().setAttribute('household_id', householdId);
  }
}

/** Log non-fatal error to Crashlytics */
export function logNonFatal(error: Error, context?: string) {
  if (context) crashlytics().log(context);
  crashlytics().recordError(error);
}

/** Add breadcrumb (last N actions before a crash) */
export function logBreadcrumb(message: string) {
  crashlytics().log(message);
}

// ---------------------------------------------------------------------------
// Analytics — Core business events
// ---------------------------------------------------------------------------

export async function logHouseholdCreated(householdType: string, memberCount: number) {
  await analytics().logEvent('household_created', {
    household_type: householdType,
    member_count: memberCount,
  });
}

export async function logHouseholdJoined(inviteMethod: string, householdType: string) {
  await analytics().logEvent('household_joined', {
    invite_method: inviteMethod,
    household_type: householdType,
  });
}

export async function logModuleFirstUse(moduleName: string) {
  await analytics().logEvent('module_first_use', { module_name: moduleName });
}

export async function logGrocerySessionStarted(itemCount: number) {
  await analytics().logEvent('grocery_session_started', { item_count: itemCount });
}

export async function logGrocerySessionCompleted(
  itemCount: number,
  durationSeconds: number,
  expenseCreated: boolean,
) {
  await analytics().logEvent('grocery_session_completed', {
    item_count: itemCount,
    duration_seconds: durationSeconds,
    expense_created: expenseCreated ? 'true' : 'false',
  });
}

export async function logExpenseCreated(
  source: 'manual' | 'grocery' | 'recurring',
  splitType: string,
  amountRange: string,
) {
  await analytics().logEvent('expense_created', {
    source,
    split_type: splitType,
    amount_range: amountRange,
  });
}

export async function logExpenseSettled(settlementCount: number, totalAmountRange: string) {
  await analytics().logEvent('expense_settled', {
    settlement_count: settlementCount,
    total_amount_range: totalAmountRange,
  });
}

export async function logMealSlotClaimed(slotType: string, dayOffset: number) {
  await analytics().logEvent('meal_slot_claimed', {
    slot_type: slotType,
    day_offset: dayOffset,
  });
}

export async function logChoreCompleted(wasAssigned: boolean, daysOverdue: number) {
  await analytics().logEvent('chore_completed', {
    was_assigned_to_completer: wasAssigned ? 'true' : 'false',
    days_overdue: daysOverdue,
  });
}

// ---------------------------------------------------------------------------
// User properties (set once, update on change)
// ---------------------------------------------------------------------------

export async function setUserProperties(props: {
  householdType?: string;
  householdSize?: number;
  modulesEnabled?: string[];
  isAdmin?: boolean;
}) {
  if (props.householdType) {
    await analytics().setUserProperty('household_type', props.householdType);
  }
  if (props.householdSize !== undefined) {
    await analytics().setUserProperty('household_size', String(props.householdSize));
  }
  if (props.modulesEnabled) {
    await analytics().setUserProperty('modules_enabled', props.modulesEnabled.join(','));
  }
  if (props.isAdmin !== undefined) {
    await analytics().setUserProperty('is_admin', String(props.isAdmin));
  }
}

// ---------------------------------------------------------------------------
// Analytics opt-out (GDPR)
// ---------------------------------------------------------------------------

export async function setAnalyticsEnabled(enabled: boolean) {
  await analytics().setAnalyticsCollectionEnabled(enabled);
  await crashlytics().setCrashlyticsCollectionEnabled(enabled);
}
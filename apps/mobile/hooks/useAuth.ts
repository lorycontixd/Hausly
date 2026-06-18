import { useEffect, useState, useCallback, useRef } from "react";
import { FirebaseAuthTypes } from "@react-native-firebase/auth";
import { setCrashUser, logBreadcrumb, logNonFatal } from '@/services/analytics';

import {
  onAuthStateChanged,
  signInWithGoogle,
  signInWithApple,
  signInWithEmail,
  createAccountWithEmail,
  signOut as firebaseSignOut,
  getIdToken,
} from "@/services/firebase";
import {
  clearUserContext,
  setUserContext,
  trackEvent,
  trackException,
  trackWarning,
} from "@/services/telemetry";
import { verifyToken, VerifyResponse } from "@/services/api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  user: FirebaseAuthTypes.User | null;
  profile: VerifyResponse | null;
  profileLoaded: boolean;
  error: string | null;
}

const MAX_VERIFY_RETRIES = 3;
const VERIFY_RETRY_DELAY_MS = 1500;

async function verifyWithRetry(): Promise<VerifyResponse> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= MAX_VERIFY_RETRIES; attempt++) {
    try {
      return await verifyToken();
    } catch (e) {
      lastError = e;
      console.warn(
        `[useAuth] verifyToken attempt ${attempt}/${MAX_VERIFY_RETRIES} failed:`,
        e instanceof Error ? e.message : e,
      );
      trackWarning(`verifyToken attempt ${attempt} failed`, {
        attempt: String(attempt),
        error: e instanceof Error ? e.message : String(e),
      });
      if (attempt < MAX_VERIFY_RETRIES) {
        await new Promise((r) => setTimeout(r, VERIFY_RETRY_DELAY_MS));
      }
    }
  }
  throw lastError;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
    profile: null,
    profileLoaded: false,
    error: null,
  });
  const verifyAbortRef = useRef<boolean>(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(async (firebaseUser) => {
      verifyAbortRef.current = true;
      verifyAbortRef.current = false;

      if (firebaseUser) {
        setState((prev) => ({
          ...prev,
          status: "authenticated",
          user: firebaseUser,
          profileLoaded: false,
        }));

        try {
          const profile = await verifyWithRetry();
          if (!verifyAbortRef.current) {
            setUserContext(firebaseUser.uid, profile.households?.[0]?.id);
            setCrashUser(firebaseUser.uid, profile.households?.[0]?.id);
            setState({
              status: "authenticated",
              user: firebaseUser,
              profile,
              profileLoaded: true,
              error: null,
            });
          }
        } catch (e) {
          console.error(
            "[useAuth] verifyToken failed after all retries:",
            e instanceof Error ? e.message : e,
          );
          trackException(
            e instanceof Error ? e : new Error(String(e)),
            { context: "verifyToken_exhausted" },
          );
          logNonFatal(
            e instanceof Error ? e : new Error(String(e)),
            "verifyToken exhausted all retries",
          );
          if (!verifyAbortRef.current) {
            setState({
              status: "authenticated",
              user: firebaseUser,
              profile: null,
              profileLoaded: true,
              error: "Failed to verify with backend",
            });
          }
        }
      } else {
        clearUserContext();
        setState({
          status: "unauthenticated",
          user: null,
          profile: null,
          profileLoaded: false,
          error: null,
        });
      }
    });

    return unsubscribe;
  }, []);

  const signInGoogle = useCallback(async () => {
    setState((prev) => ({ ...prev, error: null }));
    try {
      await signInWithGoogle();
      trackEvent("sign_in", { method: "google" });
      logBreadcrumb("sign_in:google");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Google Sign-In failed";
      trackException(e instanceof Error ? e : new Error(message), { method: "google" });
      logNonFatal(e instanceof Error ? e : new Error(message), "Google Sign-In failed");
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const signInApple = useCallback(async () => {
    setState((prev) => ({ ...prev, error: null }));
    try {
      await signInWithApple();
      trackEvent("sign_in", { method: "apple" });
      logBreadcrumb("sign_in:apple");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Apple Sign-In failed";
      trackException(e instanceof Error ? e : new Error(message), { method: "apple" });
      logNonFatal(e instanceof Error ? e : new Error(message), "Apple Sign-In failed");
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const signInEmail = useCallback(async (email: string, password: string) => {
    setState((prev) => ({ ...prev, error: null }));
    try {
      await signInWithEmail(email, password);
      trackEvent("sign_in", { method: "email" });
      logBreadcrumb("sign_in:email");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Email Sign-In failed";
      trackException(e instanceof Error ? e : new Error(message), { method: "email" });
      logNonFatal(e instanceof Error ? e : new Error(message), "Email Sign-In failed");
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const createAccount = useCallback(async (email: string, password: string) => {
    setState((prev) => ({ ...prev, error: null }));
    try {
      await createAccountWithEmail(email, password);
      trackEvent("account_created", { method: "email" });
      logBreadcrumb("account_created:email");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Account creation failed";
      trackException(e instanceof Error ? e : new Error(message), { context: "create_account" });
      logNonFatal(e instanceof Error ? e : new Error(message), "Account creation failed");
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const signOut = useCallback(async () => {
    clearUserContext();
    trackEvent("sign_out");
    await firebaseSignOut();
  }, []);

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await verifyWithRetry();
      setState((prev) => ({ ...prev, profile, profileLoaded: true }));
    } catch (e) {
      console.error("[useAuth] refreshProfile failed:", e instanceof Error ? e.message : e);
    }
  }, []);

  const hasHousehold = (state.profile?.households?.length ?? 0) > 0;

  return {
    ...state,
    signInGoogle,
    signInApple,
    signInEmail,
    createAccount,
    signOut,
    getIdToken,
    hasHousehold,
    refreshProfile,
  };
}

export type AuthContextValue = ReturnType<typeof useAuth>;

import { useEffect, useState, useCallback } from "react";
import { FirebaseAuthTypes } from "@react-native-firebase/auth";
import {
  onAuthStateChanged,
  signInWithGoogle,
  signInWithApple,
  signInWithEmail,
  createAccountWithEmail,
  signOut as firebaseSignOut,
  getIdToken,
} from "@/services/firebase";
import { verifyToken, VerifyResponse } from "@/services/api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  user: FirebaseAuthTypes.User | null;
  profile: VerifyResponse | null;
  error: string | null;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
    profile: null,
    error: null,
  });

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(async (firebaseUser) => {
      if (firebaseUser) {
        try {
          const profile = await verifyToken();
          setState({
            status: "authenticated",
            user: firebaseUser,
            profile,
            error: null,
          });
        } catch {
          setState({
            status: "authenticated",
            user: firebaseUser,
            profile: null,
            error: "Failed to verify with backend",
          });
        }
      } else {
        setState({
          status: "unauthenticated",
          user: null,
          profile: null,
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
    } catch (e) {
      const message = e instanceof Error ? e.message : "Google Sign-In failed";
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const signInApple = useCallback(async () => {
    setState((prev) => ({ ...prev, error: null }));
    try {
      await signInWithApple();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Apple Sign-In failed";
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const signInEmail = useCallback(async (email: string, password: string) => {
    setState((prev) => ({ ...prev, error: null }));
    try {
      await signInWithEmail(email, password);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Email Sign-In failed";
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const createAccount = useCallback(async (email: string, password: string) => {
    setState((prev) => ({ ...prev, error: null }));
    try {
      await createAccountWithEmail(email, password);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Account creation failed";
      setState((prev) => ({ ...prev, error: message }));
    }
  }, []);

  const signOut = useCallback(async () => {
    await firebaseSignOut();
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
  };
}

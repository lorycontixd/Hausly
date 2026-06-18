import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MUTATION_RETRY, QUERY_GC_TIME, QUERY_RETRY, QUERY_STALE_TIME } from "@/constants/query";
import { ReactNode } from "react";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: QUERY_STALE_TIME,
      gcTime: QUERY_GC_TIME,
      retry: QUERY_RETRY,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: MUTATION_RETRY,
    },
  },
});

interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

export { queryClient };

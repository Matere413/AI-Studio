// ─── Auth Context ──────────────────────────────────────────────
// Standalone context object so provider and useAuth can both import
// it without a circular dependency (provider → useAuth → provider).

import { createContext } from "react";
import type { UseAuthValue } from "./use-auth.ts";

export const AuthContext = createContext<UseAuthValue | null>(null);
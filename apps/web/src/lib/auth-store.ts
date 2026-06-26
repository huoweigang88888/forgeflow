/**
 * ForgeFlow — Auth Store (Zustand + localStorage persistence).
 *
 * Client-side auth state for Shopify OAuth.  The JWT is persisted
 * to localStorage so it survives page refreshes.
 *
 * Usage:
 *   const { token, isAuthenticated, setToken, clearToken } = useAuthStore();
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
	/** ForgeFlow JWT (NOT the Shopify access token). */
	token: string | null;
	/** The connected Shopify store domain. */
	shopDomain: string | null;
	/** True while the OAuth redirect is in progress. */
	isConnecting: boolean;

	setToken: (token: string, shopDomain: string) => void;
	clearToken: () => void;
	setConnecting: (connecting: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
	persist(
		(set, get) => ({
			token: null,
			shopDomain: null,
			isConnecting: false,

			setToken: (token, shopDomain) =>
				set({
					token,
					shopDomain,
					isConnecting: false,
				}),

			clearToken: () =>
				set({
					token: null,
					shopDomain: null,
					isConnecting: false,
				}),

			setConnecting: (isConnecting) => set({ isConnecting }),
		}),
		{
			name: "forgeflow-auth",
			// Only persist token + shopDomain (not transient connection state)
			partialize: (state) => ({
				token: state.token,
				shopDomain: state.shopDomain,
			}),
		},
	),
);

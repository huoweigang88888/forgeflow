"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { TicketStatus, WSEvent } from "@/types";

interface UseWebSocketOptions {
	ticketId: string;
	onEvent?: (event: WSEvent) => void;
	maxRetries?: number;
}

interface UseWebSocketReturn {
	lastEvent: WSEvent | null;
	status: TicketStatus | null;
	isConnected: boolean;
	error: string | null;
}

export function useWebSocket({
	ticketId,
	onEvent,
	maxRetries = 5,
}: UseWebSocketOptions): UseWebSocketReturn {
	const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
	const [derivedStatus, setDerivedStatus] = useState<TicketStatus | null>(null);
	const [isConnected, setIsConnected] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const wsRef = useRef<WebSocket | null>(null);
	const retriesRef = useRef(0);
	const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const mountedRef = useRef(true);

	const connect = useCallback(() => {
		if (!mountedRef.current) return;
		if (wsRef.current?.readyState === WebSocket.OPEN) return;

		// Connect directly to the API server for WebSocket (Next.js rewrites
		// don't support WebSocket upgrade, so we bypass the proxy).
		const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
		const apiUrl = new URL(apiBase);
		const protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
		const url = `${protocol}//${apiUrl.host}/ws/v1/tickets/${ticketId}`;

		let ws: WebSocket;
		try {
			ws = new WebSocket(url);
			wsRef.current = ws;
		} catch {
			setError("WebSocket not supported or connection failed");
			return;
		}

		ws.onopen = () => {
			if (!mountedRef.current) return;
			setIsConnected(true);
			setError(null);
			retriesRef.current = 0;
		};

		ws.onmessage = (msg) => {
			if (!mountedRef.current) return;
			try {
				const event: WSEvent = JSON.parse(msg.data as string);
				setLastEvent(event);

				if (event.status) {
					setDerivedStatus(event.status);
				}

				onEvent?.(event);
			} catch {
				// Ignore malformed messages
			}
		};

		ws.onerror = () => {
			if (!mountedRef.current) return;
			setError("WebSocket connection error");
		};

		ws.onclose = (ev) => {
			if (!mountedRef.current) return;
			setIsConnected(false);

			// Don't retry if closed cleanly by server after completion
			if (ev.code === 1000) return;

			// Exponential backoff retry
			if (retriesRef.current < maxRetries) {
				const delay = Math.min(1000 * 2 ** retriesRef.current, 16000);
				retriesRef.current += 1;
				retryTimerRef.current = setTimeout(() => {
					connect();
				}, delay);
			} else {
				setError("WebSocket disconnected — max retries exceeded");
			}
		};
	}, [ticketId, onEvent, maxRetries]);

	useEffect(() => {
		mountedRef.current = true;
		connect();

		return () => {
			mountedRef.current = false;
			if (retryTimerRef.current) {
				clearTimeout(retryTimerRef.current);
			}
			if (wsRef.current) {
				wsRef.current.close(1000, "Component unmounted");
				wsRef.current = null;
			}
		};
	}, [connect]);

	return {
		lastEvent,
		status: derivedStatus,
		isConnected,
		error,
	};
}

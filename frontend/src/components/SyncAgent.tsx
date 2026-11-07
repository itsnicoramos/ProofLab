"use client";

// Runs the progress sync (lib/sync.ts) in the background on every page: on load, a moment
// after any change, when the tab comes back into view or the network returns, and every 30 s.

import { useEffect } from "react";

import { OUTBOX_EVENT } from "@/lib/outbox";
import { syncNow } from "@/lib/sync";

export function SyncAgent() {
  useEffect(() => {
    let timer: number | undefined;
    const soon = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void syncNow(), 1200);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") void syncNow();
    };
    void syncNow();
    const every = window.setInterval(() => void syncNow(), 30_000);
    window.addEventListener(OUTBOX_EVENT, soon);
    window.addEventListener("online", soon);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(every);
      window.removeEventListener(OUTBOX_EVENT, soon);
      window.removeEventListener("online", soon);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  return null;
}

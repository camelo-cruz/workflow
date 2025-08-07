import { useEffect, useRef } from "react";

const TOKEN_KEY = "access_token";
const ONE_DRIVE_POPUP_URL = "/api/auth/start";

type LogType = "info" | "success" | "error" | "warning";

export function useOneDriveAuth(
  setIsConnected: (v: boolean) => void,
  addLog: (message: string, type?: LogType) => void,
) {
  // guard to restore token only once
  const restoredRef = useRef(false);

  // 1) On mount: restore any existing token exactly once
  useEffect(() => {
    if (!restoredRef.current) {
      const token = localStorage.getItem(TOKEN_KEY);
      if (token) {
        setIsConnected(true);
        addLog("Restored OneDrive token", "success");
      }
      restoredRef.current = true;
    }
  }, [setIsConnected, addLog]);

  // 2) Listen for storage events once
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === TOKEN_KEY && e.newValue) {
        setIsConnected(true);
        addLog("OneDrive connected via storage event", "success");
        window.removeEventListener("storage", onStorage);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [setIsConnected, addLog]);

  // 3) ALSO listen for postMessage from the popup once
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "onedrive_connected") {
        const token = localStorage.getItem(TOKEN_KEY);
        if (token) {
          setIsConnected(true);
          addLog("OneDrive connected via postMessage", "success");
          window.removeEventListener("message", onMessage);
        }
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [setIsConnected, addLog]);

  const connect = () => {
    addLog("Opening OneDrive auth…");
    window.open(ONE_DRIVE_POPUP_URL, "authPopup", "width=600,height=700");
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setIsConnected(false);
    addLog("Logged out of OneDrive", "info");
  };

  const getToken = () => localStorage.getItem(TOKEN_KEY);

  return { connect, logout, getToken };
}

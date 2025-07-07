
import { useEffect, useRef } from "react";

type LogType = "info" | "success" | "error" | "warning";

// Storage keys
const JOB_KEY = "job_id";

export function useStreamer(
  addLog: (msg: string, type?: LogType) => void,
  setIsProcessing: (v: boolean) => void,
  prefix: "inference" | "train"
) {
  const evtRef = useRef<EventSource | null>(null);

  const finish = () => {
    evtRef.current?.close();
    evtRef.current = null;
    setIsProcessing(false);
    localStorage.removeItem(JOB_KEY);
  };

  const open = (jobId: string) => {
    localStorage.setItem(JOB_KEY, jobId);
    addLog(`Opened job ${jobId}`, "info");
    setIsProcessing(true);

    const evt = new EventSource(`api/${prefix}/${jobId}/stream`);
    evtRef.current = evt;

    evt.onmessage = (e) => {
      const data = e.data;
      if (data === "[PING]") return;
      if (data.includes("[ERROR]")) {
        addLog(data, "error");
        finish();
      } else if (data.includes("[DONE ALL]")) {
        addLog("Workflow completed successfully!", "success");
        finish();
      } else {
        addLog(data, "info");
      }
    };
  };
  
    const cancel = () => {
      const jobId = localStorage.getItem(JOB_KEY);
      if (!jobId) return;
      fetch(`/${prefix}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId }),
        credentials: "same-origin",
      }).then(() => {
        addLog("Cancelled", "warning");
        finish();
      });
    };
  
    useEffect(() => {
      const pending = localStorage.getItem(JOB_KEY);
      if (pending) open(pending);
      return () => evtRef.current?.close();
    }, []);
  
    return { open, cancel };
  }
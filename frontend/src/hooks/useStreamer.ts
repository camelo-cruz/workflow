import { add } from "date-fns";
import { useEffect, useRef } from "react";

type LogType = "info" | "success" | "error" | "warning";

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

    const evt = new EventSource(`/api/${prefix}/${jobId}/stream`);
    evtRef.current = evt;

    evt.onmessage = async (e) => {
    const data = e.data;
    if (data === "[PING]") return;

    if (data.includes("[ERROR]")) {
      addLog(data, "error");
      return finish();
    }

    if (data === "[DONE ALL]") {
      addLog("Workflow completed successfully!", "success");
      if (prefix === "inference") {
        const downloadUrl = `/api/${prefix}/${jobId}/download`;
        try {
          // try to GET the zip; if it 404s, this'll go to catch
          const res = await fetch(downloadUrl);
          if (!res.ok) throw new Error(`No ZIP (status ${res.status})`);

          // pull it down as a blob…
          const blob = await res.blob();
          const blobUrl = window.URL.createObjectURL(blob);

          // …and trigger the download
          const a = document.createElement("a");
          a.href = blobUrl;
          a.download = `${jobId}_results.zip`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(blobUrl);

          addLog("Download started…", "info");
        } catch (err) {
          // either a 404 or network error → no files to download
          addLog("No files to download.");
        } finally {
          finish();
        }
      } else {
        addLog("Model saved in models!", "success");
        finish();
      }
    } else {
      addLog(data, "info");
    }
  };

  }; // ← **this** closes the open() function

  const cancel = () => {
    const jobId = localStorage.getItem(JOB_KEY);
    if (!jobId) return;
    fetch(`/api/${prefix}/cancel`, {
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

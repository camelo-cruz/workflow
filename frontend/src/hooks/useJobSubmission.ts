// Hook: job submission (online & upload)

import { useRef } from "react";
import JSZip from "jszip";

type LogType = "info" | "success" | "error" | "warning";

export function useJobSubmission(
  isProcessing: boolean,
  setIsProcessing: (v: boolean) => void,
  addLog: (m: string, t?: LogType) => void,
  streamerOpen: (jobId: string) => void,
  getToken: () => string | null,
) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const submit = async ({
    mode,
    baseDir,
    action,
    instruction,
    language,
    model,
  }: {
    mode: "online" | "upload";
    baseDir: string;
    action: string;
    instruction: string;
    language: string;
    model?: string;
  }) => {
    setIsProcessing(true);
    addLog("Submitting job…", "info");

    const form = new FormData();
    form.append("action", action);
    form.append("instruction", instruction);
    form.append("language", language);
    if (model) {
      form.append("model", model);
    }

    if (mode === "online") {
      form.append("base_dir", baseDir);
      const token = getToken();
      if (!token) {
        addLog("No OneDrive token. Please connect.", "error");
        setIsProcessing(false);
        return;
      }
      form.append("access_token", token);

      const res = await fetch("/jobs/process", {
        method: "POST",
        body: form,
        credentials: "same-origin",
      });
      if (!res.ok) {
        const errorText = await res.text();
        addLog(`Error: ${errorText}`, "error");
        setIsProcessing(false);
        return;
      }
      const { job_id } = await res.json();
      streamerOpen(job_id);
    } else {
      // offline: zip & upload
      addLog("Zipping files…", "info");
      const zip = new JSZip();
      const input = fileInputRef.current!;
      Array.from(input.files || []).forEach((f) => {
        zip.file((f as any).webkitRelativePath, f);
      });
      const blob = await zip.generateAsync({ type: "blob" }, (meta) => {
        addLog(`Zipping ${Math.round(meta.percent)}%`, "info");
      });
      form.append("zipfile", blob, "upload.zip");

      addLog("Uploading zip…", "info");
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/jobs/process");
      xhr.withCredentials = true;
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          addLog(
            `Uploading… ${Math.round((e.loaded / e.total) * 100)}%`,
            "info",
          );
        }
      };
      xhr.onload = () => {
        const { job_id } = JSON.parse(xhr.responseText);
        streamerOpen(job_id);
      };
      xhr.send(form);
    }
  };

  return { fileInputRef, submit };
}

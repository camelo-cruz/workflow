import { useRef } from "react";
import JSZip from "jszip";

type LogType = "info" | "success" | "error" | "warning";

export function useTrainSubmission(
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
    study,
    language,
  }: {
    mode: "online" | "upload";
    baseDir: string;
    action: string;
    study: string;
    language: string;
  }) => {
    setIsProcessing(true);
    addLog("Submitting job…", "info");


    const form = new FormData();
    // Backend expects `action` and `train_type`, and `base_dir`
    form.append("action", action);
    form.append("language", language);
    form.append("study", study);
    form.append("base_dir", baseDir);

    if (mode === "online") {
      const token = getToken();
      if (!token) {
        addLog("No OneDrive token. Please connect.", "error");
        setIsProcessing(false);
        return;
      }
      form.append("access_token", token);

      try {
        const res = await fetch("/train/process", {
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
        setIsProcessing(false);
        streamerOpen(job_id);
      } catch (err) {
        addLog(`Submission failed: ${err}`, "error");
        setIsProcessing(false);
      }
    } else {
      // offline: zip & upload
      addLog("Zipping files…", "info");

      try {
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
        xhr.open("POST", "/train/process");
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
          setIsProcessing(false);
          streamerOpen(job_id);
        };
        xhr.onerror = () => {
          addLog("Upload failed.", "error");
          setIsProcessing(false);
        };
        xhr.send(form);
      } catch (zipErr) {
        addLog(`Zip generation failed: ${zipErr}`, "error");
        setIsProcessing(false);
      }
    }
  };

  return { fileInputRef, submit };
}

export async function startProcessing(elements, streamer) {
  const {
    btnProcess, btnCancel,
    fileInput, actionSelect, instruction,
    statusEl, progressEl, getAccessToken
  } = elements;

  btnProcess.onclick = async () => {
    btnProcess.hidden = true;
    btnCancel.hidden  = false;

    const mode = document.querySelector('input[name="mode"]:checked').value;
    const data = new FormData();
    data.append("action", actionSelect.value);
    data.append("instruction", instruction.value);
    const langEl = document.getElementById('language');
    const lang   = langEl.value.trim();
    if (!lang) {
      statusEl.textContent = "Please select a language.";
      btnProcess.hidden = false;
      btnCancel.hidden = true;
      langEl.focus();
      return;
    }
    data.append("language", lang);

    if (mode === 'online') {
      data.append("base_dir", document.getElementById('remote-base-dir').value);
      data.append("access_token", getAccessToken());
      const res = await fetch("/jobs/process", {
        method: "POST",
        body: data,
        credentials: "same-origin"
      });
      if (!res.ok) {
        const error = await res.text();
        statusEl.textContent = `Error: ${error}`;
        btnProcess.hidden = false;
        btnCancel.hidden  = true;
        return;
      }
      const { job_id } = await res.json();
      streamer.open(job_id);
    } else {
      // offline: zip & upload
      statusEl.textContent = "Zipping…";
      const zip = new JSZip();
      Array.from(fileInput.files).forEach(f => zip.file(f.webkitRelativePath, f));
      const blob = await zip.generateAsync({ type: "blob" }, meta => {
        progressEl.hidden = false;
        progressEl.value  = meta.percent;
        statusEl.textContent = `Zipping ${Math.round(meta.percent)}%`;
      });
      data.append("zipfile", blob, "upload.zip");

      statusEl.textContent = "Uploading…";
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/jobs/process");
      xhr.withCredentials = true;
      xhr.upload.onprogress = e => {
        if (e.lengthComputable) {
          progressEl.value = (e.loaded / e.total) * 100;
          statusEl.textContent = `Uploading… ${Math.round(progressEl.value)}%`;
        }
      };
      xhr.onload = () => {
        const { job_id } = JSON.parse(xhr.responseText);
        streamer.open(job_id);
      };
      xhr.send(data);
    }
  };

  btnCancel.onclick = async () => {
    await fetch("/jobs/cancel", {
      method: "POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify({ job_id: streamer.jobId }),
      credentials: "same-origin"
    });
    streamer.cancel();
  };
}

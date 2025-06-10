// streamer.js
export class Streamer {
  constructor({ btnProcess, btnCancel, statusEl, progressEl, logsEl }) {
    this.btnProcess = btnProcess;
    this.btnCancel  = btnCancel;
    this.statusEl   = statusEl;
    this.progressEl = progressEl;
    this.logsEl     = logsEl;
    this.evt        = null;
    this.jobId      = null;
  }

  open(jobId) {
    this.jobId = jobId;
    localStorage.setItem("job_id", jobId);
    this.btnProcess.hidden = true;
    this.btnCancel.hidden  = false;
    this.progressEl.hidden = true;
    this.statusEl.textContent = `Job ${jobId}`;
    this.logsEl.textContent = "";

    this.evt = new EventSource(`/stream/${jobId}/`);
    this.evt.onmessage = e => {
      const msg = e.data;
      if (msg === "[PING]") return;
      this.logsEl.textContent += msg + "\n";

      if (msg.includes("[DONE ALL]") || msg.includes("[ERROR]")) {
        this.finish();
      }
    };
  }

  finish() {
    this.evt.close();
    this.btnCancel.hidden  = true;
    this.btnProcess.hidden = false;
    localStorage.removeItem("job_id");
    this.statusEl.textContent = 'finished';
    // download if offline:
    if (document.querySelector('input[name="mode"]:checked').value === 'upload') {
      fetch(`download/${this.jobId}/`)
        .then(r => r.blob())
        .then(blob => {
          const url = URL.createObjectURL(blob);
          const a   = document.createElement('a');
          a.href    = url;
          a.download = `${this.jobId}_results.zip`;
          document.body.append(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        })
        .catch(console.error);
    }
  }

  cancel() {
    if (this.evt) this.evt.close();
    this.statusEl.textContent = "Cancelled";
    this.btnCancel.hidden   = true;
    this.btnProcess.hidden  = false;
    localStorage.removeItem("job_id");
  }
}

// main.js
import { initUI } from './ui.js';
import { startProcessing } from './processor.js';
import { Streamer } from './streamer.js';

window.addEventListener('load', () => {
  const els = initUI();
  const streamer = new Streamer({
    btnProcess: els.btnProcess,
    btnCancel:  els.btnCancel,
    statusEl:   els.statusEl,
    progressEl: els.progressEl,
    logsEl:     document.getElementById('logs')
  });
  startProcessing(els, streamer);

  // If there’s a stored job on reload, resume streaming
  const pending = localStorage.getItem('job_id');
  if (pending) {
    streamer.open(pending);
  }
});

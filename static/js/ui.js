// ui.js
import { initAuth, getAccessToken } from './auth.js';

export function initUI() {
  const modeRadios    = document.querySelectorAll('input[name="mode"]');
  const onlineUI      = document.getElementById('online-ui');
  const uploadUI      = document.getElementById('upload-ui');
  const fileInput     = document.getElementById('file-input');
  const btnUpload     = document.getElementById('btn-upload-folder');
  const btnProcess    = document.getElementById('btn-process');
  const btnCancel     = document.getElementById('btn-cancel');
  const statusEl      = document.getElementById('status');
  const progressEl    = document.getElementById('upload-progress');
  const actionSelect  = document.getElementById('action');
  const instruction   = document.getElementById('instruction');
  const instructionLabel = document.querySelector('label[for="instruction"]');
  const connectBtn    = document.getElementById('btn-connect');
  const manualInput   = document.getElementById('manual-token');
  const setTokenBtn   = document.getElementById('btn-set-token');

  initAuth(connectBtn, manualInput, setTokenBtn, statusEl);

  // mode switching
  function onModeChange() {
    const isUpload = document.querySelector('input[name="mode"]:checked').value === 'upload';
    onlineUI.style.display = isUpload ? 'none' : 'block';
    uploadUI.style.display = isUpload ? 'block' : 'none';
    btnProcess.disabled   = isUpload ? !fileInput.files.length : false;
  }
  modeRadios.forEach(r => r.addEventListener('change', onModeChange));
  onModeChange();

  // file picker
  btnUpload.onclick = () => fileInput.click();
  fileInput.onchange = () => {
    btnProcess.disabled = fileInput.files.length === 0;
  };

  // show/hide instruction dropdown
  function updateInstructionVisibility() {
    const show = actionSelect.value === 'gloss' || actionSelect.value === 'translate';
    instruction.style.display      = show ? 'block' : 'none';
    instructionLabel.style.display = show ? 'block' : 'none';
  }
  actionSelect.addEventListener('change', updateInstructionVisibility);
  updateInstructionVisibility();

  return {
    btnProcess, btnCancel, statusEl, progressEl,
    fileInput, actionSelect, instruction, getAccessToken
  };
}

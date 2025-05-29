const modeRadios = document.querySelectorAll('input[name="mode"]');
const onlineUI = document.getElementById('online-ui');

const remoteBaseDir = document.getElementById('remote-base-dir');
const uploadUI = document.getElementById('upload-ui');
const fileInput = document.getElementById('file-input');
const btnUpload = document.getElementById('btn-upload-folder');
const btnProcess = document.getElementById('btn-process');
const btnCancel = document.getElementById('btn-cancel');
const statusEl = document.getElementById('status');
const progressEl = document.getElementById('upload-progress');
const form = document.getElementById('form-transcribe');
const actionSelect = document.getElementById('action');
const instructionSelect = document.getElementById('instruction');
const instructionLabel  = document.querySelector('label[for="instruction"]');

const connectBtn = document.getElementById('btn-connect');
const manualInput = document.getElementById('manual-token');
const setTokenBtn = document.getElementById('btn-set-token');

let uploadFiles = [], jobId = null, evt = null;
var accessToken = null;

// 1. Authentication handling

window.addEventListener('storage', (evt) => {
  if (evt.key === 'access_token' && evt.newValue) {
    setToken(evt.newValue);
    localStorage.removeItem('access_token');
  }
});

connectBtn.addEventListener('click', () => {
    manualInput.style.display = 'block';
    setTokenBtn.style.display = 'block';
    statusEl.textContent = 'Connection to OneDrive in Progress...';
    window.open('/auth/start', 'authPopup', 'width=600,height=700');
}); 

  function setToken(token) {
    accessToken = token;
    localStorage.setItem('access_token', token);

    connectBtn.style.display  = 'none';
    manualInput.style.display = 'none';
    setTokenBtn.style.display = 'none';
    btnProcess.disabled       = false;
    statusEl.textContent      = 'OneDrive connected.';
  }

setTokenBtn.addEventListener('click', () => {
    const t = manualInput.value.trim();
    if (!t) return alert('Please paste a valid token.');
    setToken(t);
});

window.addEventListener("load", () => {
    jobId       = localStorage.getItem("job_id");
    accessToken = localStorage.getItem("access_token");
    const logs  = localStorage.getItem("logs");
    if (logs) {
        document.getElementById("logs").textContent = logs;
    }
    if (jobId) {
        openStream();
    }
});

// On load, check if we have a job ID and access token
window.addEventListener("load", () => {
    jobId       = localStorage.getItem("job_id");
    accessToken = localStorage.getItem("access_token");
    const logs  = localStorage.getItem("logs");
    if (logs) {
        document.getElementById("logs").textContent = logs;
    }
    if (jobId) {
        openStream();
    }
});


// 2. Processing handling

// Selecting processing mode
function onModeChange() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    isOffline = (mode === 'upload');
    onlineUI.style.display = isOffline ? 'none' : 'block';
    uploadUI.style.display = isOffline ? 'block' : 'none';
}
modeRadios.forEach(r => r.addEventListener('change', onModeChange));

btnUpload.onclick = ()=> fileInput.click();
fileInput.onchange = ()=>{
    uploadFiles = Array.from(fileInput.files);
    console.log("Picked:", uploadFiles.map(f=>f.webkitRelativePath));
    btnProcess.disabled = !uploadFiles.length;
};

function updateInstructionVisibility() {
    const show = (actionSelect.value === 'gloss' || actionSelect.value === 'translate');
    instructionSelect.style.display = show ? 'block' : 'none';
    instructionLabel .style.display = show ? 'block' : 'none';
}

actionSelect.addEventListener('change', updateInstructionVisibility);
updateInstructionVisibility();


// Processing logic
  btnProcess.onclick = async ()=>{
    btnProcess.hidden = true;
    btnCancel.hidden = false;
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const data = new FormData();
    data.append("action", document.getElementById('action').value);
    data.append("instruction", document.getElementById('instruction').value);
    data.append("language", document.getElementById('language').value);
  
    if (mode==='online') {
      data.append("base_dir", document.getElementById('remote-base-dir').value);
      data.append("access_token", accessToken);
      console.log("Using access token:", accessToken);
      // normal fetch
      const res = await fetch("/process/",{method:"POST",body:data,credentials:"same-origin"});
      const js  = await res.json();
      jobId = js.job_id;
      localStorage.setItem("job_id", jobId);
      openStream();
    } else {
      // ZIP client-side
      statusEl.textContent = "Zipping…";
      const zip = new JSZip();
      uploadFiles.forEach(f=> zip.file(f.webkitRelativePath, f));
      const blob = await zip.generateAsync({type:"blob"}, meta=>{
        progressEl.hidden = false;
        progressEl.value  = meta.percent;
        statusEl.textContent = `Zipping ${Math.round(meta.percent)}%`;
      });
      data.append("zipfile", blob, "upload.zip");
  
      // upload ZIP
      statusEl.textContent = "Uploading…";
      const xhr = new XMLHttpRequest();
      xhr.open("POST","/process/"); xhr.withCredentials=true;
      xhr.upload.onprogress = e=>{
        if(e.lengthComputable){
          progressEl.value = (e.loaded/e.total)*100;
          statusEl.textContent = `Uploading… ${Math.round(progressEl.value)}%`;
        }
      };
      xhr.onload = ()=>{
        const js=JSON.parse(xhr.responseText);
        jobId=js.job_id;
        localStorage.setItem("job_id", jobId);
        openStream();
      };
      xhr.send(data);
    }
  };
  
  function openStream() {
  btnProcess.hidden = true;
  btnCancel.hidden = false;
  progressEl.hidden = true;
  statusEl.textContent = `Job ${jobId}`;
  evt = new EventSource(`/stream/${jobId}/`);

  evt.onmessage = (e) => {
    const msg = e.data;
    if (msg === "[PING]") return;

    document.getElementById('logs').textContent += msg + "\n";

    // Handle server messages
    if (msg.includes("[DONE ALL]") || msg.includes("[ERROR]")) {
      statusEl.textContent = "Done all!";
      finishStream();  // Call cleanup and download
    }
  };

  function finishStream() {
    evt.close();
    btnCancel.hidden = true;
    btnProcess.hidden = false;
    localStorage.removeItem("job_id");
    localStorage.removeItem("logs");

    if (document.querySelector('input[name="mode"]:checked').value === 'upload') {
      fetch(`download/${jobId}/`)
        .then(r => {
          if (!r.ok) throw new Error("Download failed");
          return r.blob();
        })
        .then(blob => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${jobId}_results.zip`;
          document.body.append(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        })
        .catch(err => console.error("Download failed:", err));
    }
  }
}
  
  btnCancel.onclick = async ()=>{
    await fetch("/cancel/",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({job_id:jobId}),credentials:"same-origin"});
    evt.close();
    statusEl.textContent="Cancelled";
    btnCancel.hidden=true; btnProcess.hidden=false;
  };
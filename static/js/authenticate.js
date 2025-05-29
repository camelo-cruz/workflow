const connectBtn = document.getElementById('btn-connect');
const manualInput = document.getElementById('manual-token');
const setTokenBtn = document.getElementById('btn-set-token');
var access_token = null;

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
    access_token = token;
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
    access_token = localStorage.getItem("access_token");
    const logs  = localStorage.getItem("logs");
    if (logs) {
        document.getElementById("logs").textContent = logs;
    }
    if (jobId) {
        openStream();
    }
});
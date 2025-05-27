const connectBtn = document.getElementById('btn-connect');
const manualInput = document.getElementById('manual-token');
const setTokenBtn = document.getElementById('btn-set-token');
const statusEl = document.getElementById('status');
const btnProcess = document.getElementById('btn-process');


connectBtn.addEventListener('click', () => {
    manualInput.style.display = 'none';
    setTokenBtn.style.display = 'none';
    const popup = window.open('/auth/start', 'authPopup', 'width=600,height=700');
    if (!popup) return showManualFallback();
    const timer = setInterval(() => {
        if (!popup || popup.closed) {
            clearInterval(timer);
            fetch('/auth/token', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(body => {
                if (body.access_token) setToken(body.access_token);
                else showManualFallback();
            })
            .catch(showManualFallback);
        }
    }, 500);
});

function showManualFallback() {
    statusEl.textContent = 'Authentication failed – paste your token';
    manualInput.style.display = 'block';
    setTokenBtn.style.display = 'block';
};

function setToken(token) {
    accessToken = token;
    localStorage.setItem('access_token', token);
    connectBtn.style.display = 'none';
    manualInput.style.display = 'none';
    setTokenBtn.style.display = 'none';
    btnProcess.disabled = false;
    statusEl.textContent = 'OneDrive connected.';
};

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
const connectBtn = document.getElementById('btn-connect');
const setTokenBtn = document.getElementById('btn-set-token');
const manualInput = document.getElementById('manual-token');

// 1) Handle incoming postMessage from popup
window.addEventListener('message', event => {
  if (event.origin !== window.location.origin) return;
  const { access_token } = event.data || {};
  if (access_token) {
    // real OAuth success
    applyAuthenticatedState('✅ Authenticated to OneDrive');
    persistToken(access_token);
  } else {
    showManualFallback();
  }
});

function setToken(token) {
    accessToken = token;
    localStorage.setItem('access_token', token);
    connectBtn.style.display = 'none';
    manualInput.style.display = 'none';
    setTokenBtn.style.display = 'none';
    btnProcess.disabled = false;
    statusEl.textContent = 'OneDrive connected.';
}

connectBtn.addEventListener('click', () => {
manualInput.style.display = 'none';
setTokenBtn.style.display = 'none';
statusEl.textContent = 'Connection to OneDrive in progress...';
const popup = window.open('/auth/start', 'authPopup', 'width=600,height=700');
    if (!popup) return showManualFallback();

  // fallback if no postMessage arrives in 3 min
  const fallbackTimer = setTimeout(showManualFallback, 180_000);
  window.addEventListener('message', () => clearTimeout(fallbackTimer), { once: true });
});

// Connecting to OneDrive
function showManualFallback() {
    statusEl.textContent = 'Authentication failed – paste your token';
    manualInput.style.display = 'block';
    setTokenBtn.style.display = 'block';
}

setTokenBtn.addEventListener('click', () => {
    const t = manualInput.value.trim();
    if (!t) return alert('Please paste a valid token.');
    setToken(t);
});
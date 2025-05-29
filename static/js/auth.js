// auth.js
let accessToken = null;

export function initAuth(connectBtn, manualInput, setTokenBtn, statusEl) {
  window.addEventListener('storage', evt => {
    if (evt.key === 'access_token' && evt.newValue) {
      setToken(evt.newValue, connectBtn, manualInput, setTokenBtn, statusEl);
      localStorage.removeItem('access_token');
    }
  });

  connectBtn.addEventListener('click', () => {
    manualInput.style.display = 'block';
    setTokenBtn.style.display = 'block';
    statusEl.textContent = 'Connecting to OneDrive…';
    window.open('/auth/start', 'authPopup', 'width=600,height=700');
  });

  setTokenBtn.addEventListener('click', () => {
    const t = manualInput.value.trim();
    if (!t) return alert('Please paste a valid token.');
    setToken(t, connectBtn, manualInput, setTokenBtn, statusEl);
  });

  // on load, restore token if present
  const stored = localStorage.getItem('access_token');
  if (stored) {
    setToken(stored, connectBtn, manualInput, setTokenBtn, statusEl);
  }
}

function setToken(token, connectBtn, manualInput, setTokenBtn, statusEl) {
  accessToken = token;
  localStorage.setItem('access_token', token);
  connectBtn.style.display  = 'none';
  manualInput.style.display = 'none';
  setTokenBtn.style.display = 'none';
  statusEl.textContent      = 'OneDrive connected.';
}

export function getAccessToken() {
  return accessToken;
}

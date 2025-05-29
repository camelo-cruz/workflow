// auth.js
let accessToken = null;

export function initAuth(connectBtn, logoutBtn, manualInput, setTokenBtn, statusEl) {
  // Listen for storage-based token injection
  window.addEventListener('storage', evt => {
    if (evt.key === 'access_token' && evt.newValue) {
      applyToken(evt.newValue, connectBtn, logoutBtn, manualInput, setTokenBtn, statusEl);
      localStorage.removeItem('access_token');
    }
  });

  // “Connect” button shows the manual-paste UI
  connectBtn.addEventListener('click', () => {
    manualInput.style.display  = 'block';
    setTokenBtn.style.display  = 'block';
    statusEl.textContent       = 'Connecting to OneDrive…';
    window.open('/auth/start', 'authPopup', 'width=600,height=700');
  });

  // “Use Token” button; paste from popup
  setTokenBtn.addEventListener('click', () => {
    const t = manualInput.value.trim();
    if (!t) return alert('Please paste a valid token.');
    applyToken(t, connectBtn, logoutBtn, manualInput, setTokenBtn, statusEl);
  });

  // On load: if we already have a token, apply it
  const stored = localStorage.getItem('access_token');
  if (stored) {
    applyToken(stored, connectBtn, logoutBtn, manualInput, setTokenBtn, statusEl);
  }
}

// This actually hides/shows everything once we have a token
function applyToken(token, connectBtn, logoutBtn, manualInput, setTokenBtn, statusEl) {
  accessToken = token;
  localStorage.setItem('access_token', token);

  console.log('applyToken() after:', { 
    access_token: localStorage.getItem('access_token'),
    allKeys: Object.keys(localStorage)
  });

  connectBtn.style.display     = 'none';
  logoutBtn.style.display      = 'block';
  manualInput.style.display    = 'none';
  setTokenBtn.style.display    = 'none';
  statusEl.textContent         = 'OneDrive connected.';
}

// Expose for UI so the user can log out
export function clearAccessToken(connectBtn, logoutBtn, manualInput, setTokenBtn, statusEl) {
  accessToken = null;
  localStorage.removeItem('access_token');

  console.log('clearAccessToken() after:', { 
    access_token: localStorage.getItem('access_token'),
    allKeys: Object.keys(localStorage)
  });

  connectBtn.style.display     = 'block';
  logoutBtn.style.display      = 'none';
  manualInput.style.display    = 'none';
  setTokenBtn.style.display    = 'none';
  statusEl.textContent         = 'Not connected to OneDrive';
}

export function getAccessToken() {
  return accessToken;
}

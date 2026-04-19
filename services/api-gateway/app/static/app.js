const $ = (id) => document.getElementById(id);
const SESSION_STORAGE_KEY = "backend-platform.auth.tokens.v1";
const ACCOUNT_CONTROL_IDS = [
  "chooseRegister",
  "chooseLogin",
  "chooseReset",
  "regEmail",
  "regPassword",
  "regBtn",
  "loginEmail",
  "loginPassword",
  "loginBtn",
  "resetEmail",
  "resetRequestBtn",
  "resetCode",
  "resetPassword",
  "resetConfirmBtn",
];

const state = {
  tokens: null,
  loading: false,
  needs2fa: false,
  canSetup2fa: false,
  challengeId: null,
  formMode: "register",
  qrReady: false,
};

function baseUrl() {
  const raw = $("baseUrl").value.replace(/\/+$/, "");
  if (raw) {
    return raw;
  }
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

/** When the UI is opened over http(s) (e.g. EC2 :8080), use the same origin as the API base. */
function syncGatewayBaseUrlFromPage() {
  const el = $("baseUrl");
  if (!el) return;
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    el.value = window.location.origin;
  }
}

function setStatus(message, isError) {
  const el = $("statusLine");
  el.textContent = message;
  el.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function setResult(value, isError) {
  const el = $("result");
  if (typeof value === "string") {
    el.textContent = value;
  } else {
    const safe = redactTokens(value);
    el.textContent = JSON.stringify(safe, null, 2);
  }
  el.style.color = isError ? "var(--danger)" : "var(--text)";
}

function setLoading(isLoading) {
  state.loading = isLoading;
  [
    "login2faBtn",
  ].forEach((id) => {
    const el = $(id);
    if (el) el.disabled = isLoading;
  });
  refreshAccountState();
  refreshSetupState();
}

function setTwoFaStep(visible) {
  $("twoFaStep").classList.toggle("hidden", !visible);
  state.needs2fa = visible;
}

function setSetupEnabled(enabled) {
  state.canSetup2fa = enabled;
  refreshSetupState();
}

function refreshSetupState() {
  const isSignedIn = hasActiveSession();
  const canSetup = state.canSetup2fa && Boolean(state.tokens?.access_token);
  $("setup2faBtn").disabled = !canSetup || state.loading;
  $("enable2faBtn").disabled = !isSignedIn || !state.qrReady || state.loading;
  $("logoutBtn").disabled = !state.tokens?.refresh_token || state.loading;
  $("setupNote").textContent = canSetup
    ? "Create a QR now, scan it, then enter the authenticator code."
    : "Sign in or create an account to enable 2FA.";
}

function hasActiveSession() {
  return Boolean(state.tokens?.access_token && state.tokens?.refresh_token);
}

function formGuideText(mode) {
  if (hasActiveSession()) {
    return "Active session. Sign out before creating another account, signing in, or resetting a password.";
  }
  if (mode === "register") {
    return "Register: enter your email and password, then click \"Create account\". You can enable 2FA after the account is created.";
  }
  if (mode === "login") {
    return "Login: enter your email and password, then click \"Sign in\". If 2FA is not enabled yet, you can enable it after sign-in.";
  }
  return "Reset password: request a 6-digit code by email, then enter the code and a new password.";
}

function refreshAccountState() {
  const isLocked = hasActiveSession();
  ACCOUNT_CONTROL_IDS.forEach((id) => {
    const el = $(id);
    if (el) el.disabled = isLocked || state.loading;
  });
  $("formGuide").textContent = formGuideText(state.formMode);
}

function setFormMode(mode) {
  state.formMode = mode;
  const isRegister = mode === "register";
  const isLogin = mode === "login";
  const isReset = mode === "reset";
  $("formRegister").classList.toggle("hidden", !isRegister);
  $("formLogin").classList.toggle("hidden", !isLogin);
  $("formReset").classList.toggle("hidden", !isReset);
  $("chooseRegister").classList.toggle("active", isRegister);
  $("chooseLogin").classList.toggle("active", isLogin);
  $("chooseReset").classList.toggle("active", isReset);
  refreshAccountState();
}

function bindEnter(inputIds, buttonId, isVisible) {
  inputIds.forEach((id) => {
    const input = $(id);
    if (!input) return;
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      if (typeof isVisible === "function" && !isVisible()) return;
      const btn = $(buttonId);
      if (!btn || btn.disabled) return;
      event.preventDefault();
      btn.click();
    });
  });
}

function resetQr() {
  state.qrReady = false;
  $("qrImage").classList.remove("visible");
  $("qrImage").removeAttribute("src");
  $("qrEmpty").classList.remove("hidden");
  refreshSetupState();
}

function loadStoredTokens() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const tokens = JSON.parse(raw);
    if (tokens?.access_token && tokens?.refresh_token) return tokens;
  } catch (_) {
    // Ignore malformed local state and force a clean sign-in.
  }
  localStorage.removeItem(SESSION_STORAGE_KEY);
  return null;
}

function saveTokens(tokens) {
  if (!tokens?.access_token || !tokens?.refresh_token) return;
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(tokens));
}

function clearStoredTokens() {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

function setTokens(tokens) {
  state.tokens = tokens;
  if (tokens) {
    saveTokens(tokens);
  } else {
    clearStoredTokens();
  }
  refreshAccountState();
  refreshSetupState();
}

function clearSession() {
  setTokens(null);
  state.challengeId = null;
  setTwoFaStep(false);
  setSetupEnabled(false);
  resetQr();
}

async function post(path, payload, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(baseUrl() + path, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  let body = text;
  try {
    body = JSON.parse(text);
  } catch (_) {}
  if (!res.ok) {
    if (body && typeof body === "object" && !Array.isArray(body)) {
      body.status = res.status;
    } else {
      body = { message: body || "Request failed.", status: res.status };
    }
    throw body;
  }
  return body;
}

function handleTokens(body) {
  if (body.challenge_id) state.challengeId = body.challenge_id;
  const tokens = body.access_token ? body : body.tokens;
  if (tokens?.access_token && tokens?.refresh_token) setTokens(tokens);
}

async function restoreStoredSession() {
  const stored = loadStoredTokens();
  if (!stored) {
    refreshSetupState();
    return;
  }

  setTokens(stored);
  setTwoFaStep(false);
  setSetupEnabled(true);
  setStatus("Restoring session...", false);
  setResult("Restoring session...", false);

  try {
    const body = await post("/v1/tokens/refresh", {
      refresh_token: stored.refresh_token,
    });
    handleTokens(body);
    setStatus("Session restored.", false);
    setResult({ status: "session_restored", tokens: state.tokens }, false);
  } catch (err) {
    if ([400, 401, 403].includes(err.status)) {
      clearSession();
      setStatus("Session expired. Sign in again.", true);
    } else {
      setSetupEnabled(true);
      setStatus("Session kept locally. Refresh failed.", true);
    }
    setResult(err, true);
  }
}

function redactTokens(payload) {
  const clone = JSON.parse(JSON.stringify(payload));
  if (clone.access_token) clone.access_token = "[redacted]";
  if (clone.refresh_token) clone.refresh_token = "[redacted]";
  if (clone.tokens?.access_token) clone.tokens.access_token = "[redacted]";
  if (clone.tokens?.refresh_token) clone.tokens.refresh_token = "[redacted]";
  if (clone.backup_codes) clone.backup_codes = "[redacted]";
  if (clone.qr_png_base64) clone.qr_png_base64 = "[redacted]";
  return clone;
}

function ensureAccessToken() {
  const token = state.tokens?.access_token;
  if (!token) {
    setStatus("Login required before this action.", true);
    throw { message: "Missing access token" };
  }
  return token;
}

function ensureTotp(value) {
  const code = value.trim();
  if (!/^[0-9]{6,8}$/.test(code)) {
    setStatus("TOTP code must be 6-8 digits.", true);
    throw { message: "Invalid TOTP code" };
  }
  return code;
}

$("regBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Registering...", false);
  setResult("Registering...", false);
  try {
    const password = $("regPassword").value;
    if (password.length < 8) {
      setStatus("Password must be at least 8 characters.", true);
      return;
    }
    const body = await post("/v1/auth/register", {
      email: $("regEmail").value,
      password,
    });
    handleTokens(body);
    setTwoFaStep(false);
    setSetupEnabled(true);
    $("regPassword").value = "";
    setStatus("Account created.", false);
    setResult(body, false);
  } catch (err) {
    setStatus(err.message || "Registration failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("loginBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Signing in...", false);
  setResult("Signing in...", false);
  try {
    const body = await post("/v1/auth/login", {
      email: $("loginEmail").value,
      password: $("loginPassword").value,
    });
    handleTokens(body);
    if (body.requires_2fa) {
      setStatus("2FA required. Complete the 2FA step below.", false);
      setTwoFaStep(true);
      setSetupEnabled(false);
    } else {
      setStatus("Signed in.", false);
      setTwoFaStep(false);
      setSetupEnabled(true);
    }
    setResult(body, false);
    $("loginPassword").value = "";
  } catch (err) {
    setStatus(err.message || "Login failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("resetRequestBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Sending reset email...", false);
  setResult("Sending reset email...", false);
  try {
    const email = $("resetEmail").value.trim();
    if (!email) {
      setStatus("Email is required for password reset.", true);
      return;
    }
    const body = await post("/v1/auth/password/forgot", { email });
    setStatus("If the email exists, a reset code was sent.", false);
    setResult(body, false);
  } catch (err) {
    setStatus(err.message || "Reset request failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("resetConfirmBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Resetting password...", false);
  setResult("Resetting password...", false);
  try {
    const email = $("resetEmail").value.trim();
    const code = $("resetCode").value.trim();
    const password = $("resetPassword").value;
    if (!email || !code || !password) {
      setStatus("Email, code, and new password are required.", true);
      return;
    }
    if (!/^[0-9]{6}$/.test(code)) {
      setStatus("Reset code must be 6 digits.", true);
      return;
    }
    const body = await post("/v1/auth/password/reset", {
      email,
      code,
      password,
    });
    setStatus("Password reset successful. You can sign in now.", false);
    setResult(body, false);
    $("resetCode").value = "";
    $("resetPassword").value = "";
  } catch (err) {
    setStatus(err.message || "Password reset failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("login2faBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Verifying 2FA...", false);
  setResult("Verifying 2FA...", false);
  try {
    const body = await post("/v1/auth/login/2fa", {
      challenge_id: state.challengeId,
      totp_code: $("totpCode").value || null,
      backup_code: null,
    });
    handleTokens(body);
    setStatus("2FA verified.", false);
    setTwoFaStep(false);
    setSetupEnabled(false);
    setResult(body, false);
    $("totpCode").value = "";
    state.challengeId = null;
  } catch (err) {
    setStatus(err.message || "2FA verification failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("setup2faBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Creating Google Authenticator QR...", false);
  setResult("Creating Google Authenticator QR...", false);
  try {
    if (!state.canSetup2fa) {
      setStatus("Sign in or create an account before creating a QR.", true);
      return;
    }
    const token = ensureAccessToken();
    const body = await post("/v1/two-factor/setup", {}, token);
    if (body.qr_png_base64) {
      $("qrImage").src = `data:image/png;base64,${body.qr_png_base64}`;
      $("qrImage").classList.add("visible");
      $("qrEmpty").classList.add("hidden");
      state.qrReady = true;
      refreshSetupState();
    }
    setStatus("QR created. Scan in Google Authenticator.", false);
    setResult(body, false);
  } catch (err) {
    setStatus(err.message || "2FA setup failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("enable2faBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Enabling 2FA...", false);
  setResult("Enabling 2FA...", false);
  try {
    const token = ensureAccessToken();
    const totp = ensureTotp($("enableTotpCode").value);
    const body = await post("/v1/two-factor/enable", { totp_code: totp }, token);
    if (body.backup_codes) {
      setStatus("2FA enabled. Backup codes generated.", false);
    }
    resetQr();
    setSetupEnabled(false);
    setStatus("2FA enabled.", false);
    setResult(body, false);
    $("enableTotpCode").value = "";
  } catch (err) {
    setStatus(err.message || "Enable 2FA failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("logoutBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Signing out...", false);
  setResult("Signing out...", false);
  const refresh = state.tokens?.refresh_token;
  clearSession();
  try {
    if (!refresh) {
      setStatus("No active session.", true);
      setResult({ status: "no_active_session" }, true);
      return;
    }
    const body = await post("/v1/tokens/revoke", { refresh_token: refresh });
    setStatus("Signed out.", false);
    setResult(body, false);
  } catch (err) {
    setStatus("Signed out locally. Server revoke failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

syncGatewayBaseUrlFromPage();
resetQr();
setFormMode("register");
setSetupEnabled(false);

$("chooseRegister").addEventListener("click", () => setFormMode("register"));
$("chooseLogin").addEventListener("click", () => setFormMode("login"));
$("chooseReset").addEventListener("click", () => setFormMode("reset"));

bindEnter(["regEmail", "regPassword"], "regBtn", () => !$("formRegister").classList.contains("hidden"));
bindEnter(["loginEmail", "loginPassword"], "loginBtn", () => !$("formLogin").classList.contains("hidden"));
bindEnter(["resetEmail"], "resetRequestBtn", () => !$("formReset").classList.contains("hidden"));
bindEnter(["resetCode", "resetPassword"], "resetConfirmBtn", () => !$("formReset").classList.contains("hidden"));
bindEnter(["totpCode"], "login2faBtn", () => !$("twoFaStep").classList.contains("hidden"));
bindEnter(["enableTotpCode"], "enable2faBtn");

window.addEventListener("load", () => {
  setTimeout(() => {
    [
      "regEmail",
      "regPassword",
      "loginEmail",
      "loginPassword",
      "resetEmail",
      "resetCode",
      "resetPassword",
      "displayName",
      "enableTotpCode",
      "totpCode",
    ].forEach((id) => {
      const el = $(id);
      if (el) el.value = "";
    });
    state.challengeId = null;
    void restoreStoredSession();
  }, 50);
});

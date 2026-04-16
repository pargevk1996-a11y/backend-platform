const $ = (id) => document.getElementById(id);

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
  loading: false,
  sessionActive: false,
  needs2fa: false,
  canManage2fa: false,
  challengeId: null,
  formMode: "register",
  setupWindow: null,
};

function baseUrl() {
  return $("baseUrl").value.replace(/\/+$/, "");
}

function csrfToken() {
  const prefix = "bp_csrf_token=";
  const item = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

function setStatus(message, isError) {
  const el = $("statusLine");
  el.textContent = message;
  el.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function redactSensitive(payload) {
  const clone = JSON.parse(JSON.stringify(payload));
  if (clone.access_token) clone.access_token = "[redacted]";
  if (clone.refresh_token) clone.refresh_token = "[redacted]";
  if (clone.tokens?.access_token) clone.tokens.access_token = "[redacted]";
  if (clone.tokens?.refresh_token) clone.tokens.refresh_token = "[redacted]";
  if (clone.backup_codes) clone.backup_codes = "[redacted]";
  if (clone.qr_png_base64) clone.qr_png_base64 = "[redacted]";
  return clone;
}

function setResult(value, isError) {
  const el = $("result");
  if (typeof value === "string") {
    el.textContent = value;
  } else {
    el.textContent = JSON.stringify(redactSensitive(value), null, 2);
  }
  el.style.color = isError ? "var(--danger)" : "var(--text)";
}

function hasActiveSession() {
  return state.sessionActive;
}

function setSessionActive(active) {
  state.sessionActive = active;
  state.canManage2fa = active;
  refreshAccountState();
  refreshTwoFactorState();
}

function clearSessionState() {
  state.challengeId = null;
  state.needs2fa = false;
  setTwoFaStep(false);
  setSessionActive(false);
}

function setLoading(isLoading) {
  state.loading = isLoading;
  [
    "login2faBtn",
    "setup2faBtn",
    "disable2faBtn",
    "logoutBtn",
  ].forEach((id) => {
    const el = $(id);
    if (el) el.disabled = isLoading;
  });
  refreshAccountState();
  refreshTwoFactorState();
}

function setTwoFaStep(visible) {
  $("twoFaStep").classList.toggle("hidden", !visible);
  state.needs2fa = visible;
}

function refreshTwoFactorState() {
  const enabled = state.canManage2fa && hasActiveSession();
  $("setup2faBtn").disabled = !enabled || state.loading;
  $("disable2faPassword").disabled = !enabled || state.loading;
  $("disable2faCode").disabled = !enabled || state.loading;
  $("disable2faBackup").disabled = !enabled || state.loading;
  $("disable2faBtn").disabled = !enabled || state.loading;
  $("logoutBtn").disabled = !hasActiveSession() || state.loading;
  $("setupNote").textContent = enabled
    ? "Open setup, scan the QR, then confirm the authenticator code."
    : "Sign in or create an account before managing 2FA.";
}

function formGuideText(mode) {
  if (hasActiveSession()) {
    return "Active session. Sign out before creating another account, signing in, or resetting a password.";
  }
  if (mode === "register") {
    return "Register: enter your email and password, then click \"Create account\". You can enable 2FA after the account is created.";
  }
  if (mode === "login") {
    return "Login: enter your email and password, then click \"Sign in\". Accounts lock after 3 wrong passwords until password reset.";
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

async function post(path, payload, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (options.csrf) {
    const token = csrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const res = await fetch(baseUrl() + path, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(payload || {}),
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

function handleAuthResponse(body) {
  if (body.challenge_id) state.challengeId = body.challenge_id;
  if (body.auth === "cookie" || body.status === "authenticated" || body.status === "refreshed") {
    setSessionActive(true);
  }
}

async function restoreBrowserSession() {
  if (!csrfToken()) {
    refreshTwoFactorState();
    return;
  }

  setStatus("Restoring session...", false);
  setResult("Restoring session...", false);
  try {
    const body = await post("/v1/tokens/refresh", {}, { csrf: true });
    handleAuthResponse(body);
    setStatus("Session restored.", false);
    setResult(body, false);
  } catch (err) {
    clearSessionState();
    setStatus("Session expired. Sign in again.", true);
    setResult(err, true);
  }
}

function ensureSession() {
  if (!hasActiveSession()) {
    setStatus("Login required before this action.", true);
    throw { message: "Missing browser session" };
  }
}

function ensureTotp(value) {
  const code = value.trim();
  if (!/^[0-9]{6,8}$/.test(code)) {
    setStatus("TOTP code must be 6-8 digits.", true);
    throw { message: "Invalid TOTP code" };
  }
  return code;
}

function openSetupWindow() {
  const child = window.open("", "backendPlatform2faSetup", "popup,width=460,height=680");
  if (!child) {
    setStatus("Popup blocked. Allow popups and try again.", true);
    return null;
  }
  child.document.open();
  child.document.write(`
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Enable 2FA</title>
    <style>
      body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, sans-serif; background: #151515; color: #f1f1f1; }
      main { width: min(390px, calc(100vw - 32px)); margin: 24px auto; }
      h1 { font-size: 22px; margin: 0 0 8px; letter-spacing: 0; }
      p { color: #b0b0b0; font-size: 13px; line-height: 1.5; }
      .box { border: 1px solid #333; border-radius: 6px; padding: 14px; background: #202020; }
      img { display: block; width: min(260px, 100%); height: auto; margin: 14px auto; background: white; border-radius: 6px; }
      input, button, pre { width: 100%; box-sizing: border-box; border-radius: 6px; border: 1px solid #333; padding: 10px 12px; font: inherit; }
      input, pre { background: #121212; color: #f1f1f1; }
      button { margin-top: 12px; background: #6ee7a8; color: #07120b; border: 0; font-weight: 700; }
      button:disabled { opacity: .55; }
      pre { min-height: 90px; white-space: pre-wrap; font-size: 12px; }
      .danger { color: #ff6b6b; }
      .muted { color: #b0b0b0; }
    </style>
  </head>
  <body>
    <main>
      <h1>Enable 2FA</h1>
      <p id="setupStatus" class="muted">Creating QR...</p>
      <div class="box">
        <div id="qrMount"></div>
        <input id="popupTotpCode" autocomplete="off" placeholder="Authenticator code" />
        <button id="popupEnableBtn">Enable 2FA</button>
      </div>
      <p>Backup codes are shown once after enabling.</p>
      <pre id="popupResult"></pre>
    </main>
  </body>
</html>`);
  child.document.close();
  state.setupWindow = child;
  return child;
}

function updateSetupWindowQr(child, qrBase64) {
  const qrMount = child.document.getElementById("qrMount");
  const status = child.document.getElementById("setupStatus");
  qrMount.innerHTML = `<img alt="Google Authenticator QR" src="data:image/png;base64,${qrBase64}" />`;
  status.textContent = "Scan the QR, enter the code, then enable 2FA.";
}

function formatSetupWindowResult(value) {
  if (value && Array.isArray(value.backup_codes)) {
    return `Save these backup codes now:\n\n${value.backup_codes.join("\n")}`;
  }
  return typeof value === "string" ? value : JSON.stringify(redactSensitive(value), null, 2);
}

function updateSetupWindowResult(value, isError) {
  const child = state.setupWindow;
  if (!child || child.closed) return;
  const result = child.document.getElementById("popupResult");
  const status = child.document.getElementById("setupStatus");
  result.textContent = formatSetupWindowResult(value);
  status.textContent = isError ? "2FA setup failed." : "2FA enabled.";
  status.classList.toggle("danger", Boolean(isError));
}

window.completeTwoFactorEnable = async (code) => {
  setLoading(true);
  setStatus("Enabling 2FA...", false);
  try {
    ensureSession();
    const totp = ensureTotp(code);
    const body = await post("/v1/two-factor/enable", { totp_code: totp }, { csrf: true });
    setStatus("2FA enabled. Save your backup codes.", false);
    setResult(body, false);
    updateSetupWindowResult(body, false);
  } catch (err) {
    setStatus(err.message || "Enable 2FA failed.", true);
    setResult(err, true);
    updateSetupWindowResult(err, true);
  } finally {
    setLoading(false);
  }
};

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
    handleAuthResponse(body);
    setTwoFaStep(false);
    $("regPassword").value = "";
    setStatus("Account created. Use Enable 2FA when ready.", false);
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
    handleAuthResponse(body);
    if (body.requires_2fa) {
      setStatus("2FA required. Complete the 2FA step below.", false);
      setTwoFaStep(true);
      setSessionActive(false);
    } else {
      setStatus("Signed in.", false);
      setTwoFaStep(false);
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
    const body = await post("/v1/auth/password/reset", { email, code, password });
    setStatus("Password reset successful. The account can sign in again.", false);
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
    handleAuthResponse(body);
    setStatus("2FA verified.", false);
    setTwoFaStep(false);
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
  const child = openSetupWindow();
  if (!child) return;
  setLoading(true);
  setStatus("Creating Google Authenticator QR...", false);
  setResult("Creating Google Authenticator QR...", false);
  try {
    ensureSession();
    const body = await post("/v1/two-factor/setup", {}, { csrf: true });
    if (body.qr_png_base64) {
      updateSetupWindowQr(child, body.qr_png_base64);
    }
    const button = child.document.getElementById("popupEnableBtn");
    button.addEventListener("click", () => {
      const code = child.document.getElementById("popupTotpCode").value;
      window.completeTwoFactorEnable(code);
    });
    setStatus("QR opened in a new window.", false);
    setResult(body, false);
  } catch (err) {
    setStatus(err.message || "2FA setup failed.", true);
    setResult(err, true);
    updateSetupWindowResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("disable2faBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Disabling 2FA...", false);
  setResult("Disabling 2FA...", false);
  try {
    ensureSession();
    const password = $("disable2faPassword").value;
    const code = $("disable2faCode").value.trim();
    const backup = $("disable2faBackup").value.trim();
    if (!password) {
      setStatus("Password is required to disable 2FA.", true);
      return;
    }
    if (Boolean(code) === Boolean(backup)) {
      setStatus("Provide either authenticator code or backup code.", true);
      return;
    }
    const body = await post(
      "/v1/two-factor/disable",
      {
        password,
        totp_code: code || null,
        backup_code: backup || null,
      },
      { csrf: true },
    );
    setStatus("2FA disabled.", false);
    setResult(body, false);
    $("disable2faPassword").value = "";
    $("disable2faCode").value = "";
    $("disable2faBackup").value = "";
  } catch (err) {
    setStatus(err.message || "Disable 2FA failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("logoutBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Signing out...", false);
  setResult("Signing out...", false);
  try {
    const body = await post("/v1/tokens/revoke", {}, { csrf: true });
    clearSessionState();
    setStatus("Signed out.", false);
    setResult(body, false);
  } catch (err) {
    clearSessionState();
    setStatus("Signed out locally. Server revoke failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

setFormMode("register");
setSessionActive(false);

$("chooseRegister").addEventListener("click", () => setFormMode("register"));
$("chooseLogin").addEventListener("click", () => setFormMode("login"));
$("chooseReset").addEventListener("click", () => setFormMode("reset"));

bindEnter(["regEmail", "regPassword"], "regBtn", () => !$("formRegister").classList.contains("hidden"));
bindEnter(["loginEmail", "loginPassword"], "loginBtn", () => !$("formLogin").classList.contains("hidden"));
bindEnter(["resetEmail"], "resetRequestBtn", () => !$("formReset").classList.contains("hidden"));
bindEnter(["resetCode", "resetPassword"], "resetConfirmBtn", () => !$("formReset").classList.contains("hidden"));
bindEnter(["totpCode"], "login2faBtn", () => !$("twoFaStep").classList.contains("hidden"));
bindEnter(["disable2faPassword", "disable2faCode", "disable2faBackup"], "disable2faBtn");

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
      "totpCode",
      "disable2faPassword",
      "disable2faCode",
      "disable2faBackup",
    ].forEach((id) => {
      const el = $(id);
      if (el) el.value = "";
    });
    void restoreBrowserSession();
  }, 50);
});

const $ = (id) => document.getElementById(id);
const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const SETUP_POPUP_WIDTH = 500;
const SETUP_POPUP_HEIGHT = 650;

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
  twoFactorEnabled: null,
  challengeId: null,
  formMode: "register",
  setupPopup: null,
  setupPopupOrigin: null,
  setupPopupReady: false,
  setupPopupPendingMessage: null,
  setupPopupWatcher: null,
  setupPopupRequestId: 0,
  idleTimerId: null,
};

const SETUP_POPUP_NAME = "backendPlatform2faSetup";
const SETUP_POPUP_PATH = "/ui/two-factor-setup.html";
const SETUP_POPUP_MAIN_SOURCE = "backend-platform:2fa-setup:main";
const SETUP_POPUP_CHILD_SOURCE = "backend-platform:2fa-setup:popup";

const PASSWORD_TOGGLES = [
  { inputId: "regPassword", buttonId: "toggleRegPassword" },
  { inputId: "loginPassword", buttonId: "toggleLoginPassword" },
  { inputId: "resetPassword", buttonId: "toggleResetPassword" },
  { inputId: "disable2faPassword", buttonId: "toggleDisable2faPassword" },
];

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
  if (clone.manual_entry_key) clone.manual_entry_key = "[redacted]";
  if (clone.provisioning_uri) clone.provisioning_uri = "[redacted]";
  return clone;
}

function safeResultText(value, isError) {
  if (typeof value === "string") {
    return value;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return isError ? "Request failed." : "Request completed.";
  }
  if (isError) {
    return value.message || "Request failed.";
  }
  if (Array.isArray(value.backup_codes)) {
    return "2FA enabled.";
  }
  if (value.qr_png_base64) {
    return "QR code created. Scan it, enter the authenticator code, then enable 2FA.";
  }
  if (value.requires_2fa) {
    return "2FA challenge created. Enter the authenticator code to continue.";
  }
  if (value.auth === "cookie" && value.status === "authenticated") {
    return "Browser session is active.";
  }
  if (value.auth === "cookie" && value.status === "refreshed") {
    return "Browser session restored.";
  }
  if (typeof value.message === "string" && value.message) {
    return value.message;
  }
  if (value.status === "ok") {
    return "Operation completed.";
  }
  return "Request completed.";
}

function setResult(value, isError) {
  const el = $("result");
  el.textContent = safeResultText(value, isError);
  el.style.color = isError ? "var(--danger)" : "var(--text)";
}

function hasActiveSession() {
  return state.sessionActive;
}

function setSessionActive(active) {
  state.sessionActive = active;
  state.canManage2fa = active;
  state.twoFactorEnabled = null;
  if (!active) closeSetupPopup();
  scheduleIdleTimeout();
  refreshAccountState();
  refreshTwoFactorState();
}

function clearSessionState() {
  state.challengeId = null;
  state.needs2fa = false;
  setTwoFaStep(false);
  closeSetupPopup();
  setSessionActive(false);
}

function clearIdleTimeout() {
  if (state.idleTimerId) {
    window.clearTimeout(state.idleTimerId);
    state.idleTimerId = null;
  }
}

function scheduleIdleTimeout() {
  clearIdleTimeout();
  if (!hasActiveSession()) return;
  state.idleTimerId = window.setTimeout(() => {
    void signOutForInactivity();
  }, IDLE_TIMEOUT_MS);
}

function noteUserActivity() {
  if (!hasActiveSession()) return;
  scheduleIdleTimeout();
}

function showLoggedOutState(message, isError, resultValue = message) {
  clearSessionState();
  setFormMode("login");
  setStatus(message, isError);
  setResult(resultValue, isError);
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

function setPasswordVisibility(input, button, visible) {
  input.type = visible ? "text" : "password";
  button.classList.toggle("is-active", visible);
  button.setAttribute("aria-pressed", visible ? "true" : "false");
  button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
  button.title = visible ? "Hide password" : "Show password";
}

function hidePassword(inputId) {
  const config = PASSWORD_TOGGLES.find((item) => item.inputId === inputId);
  if (!config) return;

  const input = $(config.inputId);
  const button = $(config.buttonId);
  if (!input || !button) return;

  setPasswordVisibility(input, button, false);
}

function resetPasswordVisibility() {
  PASSWORD_TOGGLES.forEach(({ inputId }) => hidePassword(inputId));
}

function syncPasswordToggleStates() {
  PASSWORD_TOGGLES.forEach(({ inputId, buttonId }) => {
    const input = $(inputId);
    const button = $(buttonId);
    if (!input || !button) return;

    button.disabled = input.disabled;
    if (input.disabled) setPasswordVisibility(input, button, false);
  });
}

function setupPasswordToggles() {
  PASSWORD_TOGGLES.forEach(({ inputId, buttonId }) => {
    const input = $(inputId);
    const button = $(buttonId);
    if (!input || !button) return;

    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => {
      if (button.disabled) return;

      const visible = input.type === "password";
      setPasswordVisibility(input, button, visible);
      input.focus({ preventScroll: true });
    });
  });

  syncPasswordToggleStates();
}

function setupPopupUrl() {
  const url = new URL(SETUP_POPUP_PATH, `${baseUrl()}/`);
  url.searchParams.set("openerOrigin", window.location.origin);
  url.searchParams.set("v", "20260418-2fa-popup-security");
  return url;
}

function setupPopupIsOpen() {
  return Boolean(state.setupPopup && !state.setupPopup.closed);
}

function cleanupSetupPopup({ refresh = true } = {}) {
  if (state.setupPopupWatcher) {
    clearInterval(state.setupPopupWatcher);
    state.setupPopupWatcher = null;
  }
  state.setupPopupRequestId += 1;
  state.setupPopup = null;
  state.setupPopupOrigin = null;
  state.setupPopupReady = false;
  state.setupPopupPendingMessage = null;
  if (refresh) refreshTwoFactorState();
}

function closeSetupPopup() {
  const popup = state.setupPopup;
  cleanupSetupPopup({ refresh: false });
  if (popup && !popup.closed) {
    popup.close();
  }
  refreshTwoFactorState();
}

function sendSetupPopupMessage(type, payload = {}, { queueUntilReady = true } = {}) {
  if (!setupPopupIsOpen() || !state.setupPopupOrigin) return false;

  const message = {
    source: SETUP_POPUP_MAIN_SOURCE,
    type,
    payload,
  };

  if (queueUntilReady && !state.setupPopupReady) {
    state.setupPopupPendingMessage = message;
    return false;
  }

  state.setupPopup.postMessage(message, state.setupPopupOrigin);
  return true;
}

function flushSetupPopupMessage() {
  if (!state.setupPopupPendingMessage || !setupPopupIsOpen() || !state.setupPopupOrigin) return;
  state.setupPopup.postMessage(state.setupPopupPendingMessage, state.setupPopupOrigin);
  state.setupPopupPendingMessage = null;
}

function setupPopupWindowFeatures() {
  const width = SETUP_POPUP_WIDTH;
  const height = SETUP_POPUP_HEIGHT;
  const screenLeft = typeof window.screenLeft === "number" ? window.screenLeft : window.screenX;
  const screenTop = typeof window.screenTop === "number" ? window.screenTop : window.screenY;
  const outerWidth = window.outerWidth || document.documentElement.clientWidth || width;
  const outerHeight = window.outerHeight || document.documentElement.clientHeight || height;
  const left = Math.max(0, Math.round(screenLeft + (outerWidth - width) / 2));
  const top = Math.max(0, Math.round(screenTop + (outerHeight - height) / 2));

  return [
    "popup=yes",
    "menubar=no",
    "toolbar=no",
    "location=no",
    "status=no",
    "resizable=yes",
    "scrollbars=yes",
    `width=${width}`,
    `height=${height}`,
    `left=${left}`,
    `top=${top}`,
  ].join(",");
}

function openSetupPopup() {
  if (setupPopupIsOpen()) {
    state.setupPopup.focus();
    return state.setupPopup;
  }
  if (state.setupPopup) cleanupSetupPopup({ refresh: false });

  const url = setupPopupUrl();
  const popup = window.open(url.href, SETUP_POPUP_NAME, setupPopupWindowFeatures());

  if (!popup) {
    setStatus("Secure setup popup was blocked. Allow popups and try again.", true);
    return null;
  }

  state.setupPopup = popup;
  state.setupPopupOrigin = url.origin;
  state.setupPopupReady = false;
  state.setupPopupPendingMessage = null;
  state.setupPopupWatcher = setInterval(() => {
    if (!setupPopupIsOpen()) cleanupSetupPopup();
  }, 500);
  popup.focus();
  refreshTwoFactorState();
  return popup;
}

async function requestSetupPopupData(reason = "open") {
  const requestId = state.setupPopupRequestId + 1;
  state.setupPopupRequestId = requestId;

  try {
    ensureSession();
  } catch (_) {
    sendSetupPopupMessage(
      "error",
      { message: "Login required before managing 2FA." },
      { queueUntilReady: false },
    );
    return;
  }

  if (!setupPopupIsOpen()) return;

  const isRefresh = reason === "refresh";
  const statusMessage = isRefresh
    ? "Refreshing secure 2FA setup..."
    : "Creating Google Authenticator QR...";
  const popupMessage = isRefresh
    ? "Generating a fresh setup secret..."
    : "Generating QR code...";

  setLoading(true);
  setStatus(statusMessage, false);
  setResult(statusMessage, false);
  sendSetupPopupMessage("loading", { message: popupMessage }, { queueUntilReady: false });

  try {
    const body = await post("/v1/two-factor/setup", {}, { csrf: true });
    if (requestId !== state.setupPopupRequestId || !setupPopupIsOpen()) return;

    sendSetupPopupMessage(
      "qr",
      {
        qrPngBase64: body.qr_png_base64 || "",
        manualEntryKey: body.manual_entry_key || "",
      },
      { queueUntilReady: false },
    );
    setStatus(
      isRefresh
        ? "Setup popup refreshed with a new QR and manual key."
        : "Setup popup opened. Scan the QR or use the manual key there, then enter the authenticator code in the popup.",
      false,
    );
    setResult(body, false);
  } catch (err) {
    if (requestId !== state.setupPopupRequestId) return;

    const message = err.message || "2FA setup failed.";

    if (err?.status === 401 || err?.status === 403) {
      showLoggedOutState(message, true, err);
      sendSetupPopupMessage("error", { message }, { queueUntilReady: false });
      return;
    }

    setStatus(message, true);
    setResult(err, true);
    sendSetupPopupMessage("error", { message }, { queueUntilReady: false });

    if (err?.status === 409) {
      await syncSessionInfo();
      window.setTimeout(() => closeSetupPopup(), 300);
    }
  } finally {
    if (requestId === state.setupPopupRequestId || !setupPopupIsOpen()) {
      setLoading(false);
      refreshTwoFactorState();
    }
  }
}

function refreshTwoFactorState() {
  const active = state.canManage2fa && hasActiveSession();
  const statusKnown = typeof state.twoFactorEnabled === "boolean";
  const canEnable = active && statusKnown && state.twoFactorEnabled === false;
  const setupOpen = setupPopupIsOpen();
  const canDisable = active && statusKnown && state.twoFactorEnabled === true;

  $("setup2faRow").classList.toggle("hidden", !canEnable);
  $("disable2faSection").classList.toggle("hidden", !canDisable);

  $("setup2faBtn").textContent = setupOpen ? "Setup popup is open" : "Enable 2FA";
  $("setup2faBtn").disabled = !canEnable || setupOpen || state.loading;
  $("disable2faPassword").disabled = !canDisable || state.loading;
  $("disable2faCode").disabled = !canDisable || state.loading;
  $("disable2faBtn").disabled = !canDisable || state.loading;
  $("logoutBtn").disabled = !hasActiveSession() || state.loading;
  syncPasswordToggleStates();
  $("setupNote").textContent = !active
    ? "Sign in or create an account before managing 2FA."
    : !statusKnown
      ? "Loading 2FA status..."
      : canEnable
        ? setupOpen
          ? "Setup popup is open. Scan the QR there or use the manual key, then enter the authenticator code."
          : "2FA is off for this account. Open the secure setup popup, scan the QR, then confirm the authenticator code."
        : "2FA is on for this account. Use the form below to disable it.";
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
  syncPasswordToggleStates();
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

async function get(path) {
  const res = await fetch(baseUrl() + path, {
    method: "GET",
    credentials: "include",
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

async function syncSessionInfo() {
  if (!hasActiveSession()) {
    state.twoFactorEnabled = null;
    refreshTwoFactorState();
    return null;
  }

  state.twoFactorEnabled = null;
  refreshTwoFactorState();
  try {
    const body = await get("/v1/sessions/me");
    state.twoFactorEnabled = Boolean(body.two_factor_enabled);
    refreshTwoFactorState();
    return body;
  } catch (_) {
    state.twoFactorEnabled = null;
    refreshTwoFactorState();
    return null;
  }
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
    await syncSessionInfo();
    setStatus("Session restored.", false);
    setResult(body, false);
  } catch (err) {
    const message =
      err?.message === "Session expired due to inactivity"
        ? "Session expired due to inactivity."
        : "Session expired. Sign in again.";
    showLoggedOutState(message, true, err);
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

async function signOutForInactivity() {
  if (!hasActiveSession()) return;
  setLoading(true);
  try {
    await post("/v1/tokens/revoke", {}, { csrf: true });
  } catch (_) {
    // Best-effort revoke. The backend also expires idle sessions server-side.
  } finally {
    showLoggedOutState("Session expired due to inactivity.", true);
    setLoading(false);
  }
}

async function signOutUser() {
  setLoading(true);
  setStatus("Signing out...", false);
  setResult("Signing out...", false);
  try {
    const body = await post("/v1/tokens/revoke", {}, { csrf: true });
    showLoggedOutState("Signed out.", false, body);
  } catch (err) {
    if (err?.status === 401 || err?.status === 403) {
      showLoggedOutState("Signed out.", false);
    } else {
      setStatus(err.message || "Sign out failed.", true);
      setResult(err, true);
    }
  } finally {
    setLoading(false);
  }
}

async function completeTwoFactorEnable(code) {
  setLoading(true);
  setStatus("Enabling 2FA...", false);
  sendSetupPopupMessage("submitting", { message: "Checking authenticator code..." }, { queueUntilReady: false });
  try {
    ensureSession();
    const totp = ensureTotp(code);
    const body = await post("/v1/two-factor/enable", { totp_code: totp }, { csrf: true });
    await syncSessionInfo();
    setStatus("2FA enabled.", false);
    setResult(body, false);
    sendSetupPopupMessage("enabled", { message: "2FA enabled. Closing setup..." }, { queueUntilReady: false });
    setTimeout(() => closeSetupPopup(), 250);
  } catch (err) {
    const message = err.message || "Enable 2FA failed.";
    setStatus(message, true);
    setResult(err, true);
    sendSetupPopupMessage("error", { message }, { queueUntilReady: false });
  } finally {
    setLoading(false);
  }
}

window.addEventListener("message", (event) => {
  const data = event.data;
  if (!data || typeof data !== "object" || data.source !== SETUP_POPUP_CHILD_SOURCE) return;
  if (state.setupPopupOrigin && event.origin !== state.setupPopupOrigin) return;
  if (state.setupPopup && event.source && event.source !== state.setupPopup) return;

  if (data.type === "ready") {
    const wasReady = state.setupPopupReady;
    state.setupPopupReady = true;
    state.setupPopupPendingMessage = null;
    if (!state.loading) {
      void requestSetupPopupData(wasReady ? "refresh" : "open");
    }
    return;
  }

  if (data.type === "submit") {
    void completeTwoFactorEnable(String(data.payload?.code || ""));
    return;
  }
});

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
    await syncSessionInfo();
    setTwoFaStep(false);
    $("regPassword").value = "";
    hidePassword("regPassword");
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
      await syncSessionInfo();
      setStatus("Signed in.", false);
      setTwoFaStep(false);
    }
    setResult(body, false);
    $("loginPassword").value = "";
    hidePassword("loginPassword");
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
    hidePassword("resetPassword");
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
    await syncSessionInfo();
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
  try {
    ensureSession();
  } catch (_) {
    return;
  }

  const popup = openSetupPopup();
  if (!popup) return;
  popup.focus();
  setStatus("Opening secure 2FA popup...", false);
  setResult("Opening secure 2FA popup...", false);
});

$("disable2faBtn").addEventListener("click", async () => {
  setLoading(true);
  setStatus("Disabling 2FA...", false);
  setResult("Disabling 2FA...", false);
  try {
    ensureSession();
    const password = $("disable2faPassword").value;
    const code = $("disable2faCode").value.trim();
    if (!password) {
      setStatus("Password is required to disable 2FA.", true);
      return;
    }
    if (!code) {
      setStatus("Authenticator code is required to disable 2FA.", true);
      return;
    }
    const body = await post(
      "/v1/two-factor/disable",
      {
        password,
        totp_code: code,
        backup_code: null,
      },
      { csrf: true },
    );
    await syncSessionInfo();
    setStatus("2FA disabled.", false);
    setResult(body, false);
    $("disable2faPassword").value = "";
    $("disable2faCode").value = "";
    hidePassword("disable2faPassword");
  } catch (err) {
    setStatus(err.message || "Disable 2FA failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

$("logoutBtn").addEventListener("click", async () => {
  await signOutUser();
});

setupPasswordToggles();
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
bindEnter(["disable2faPassword", "disable2faCode"], "disable2faBtn");

["click", "mousemove", "scroll", "touchstart"].forEach((eventName) => {
  window.addEventListener(eventName, noteUserActivity, { passive: true });
});
window.addEventListener("keydown", noteUserActivity);

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
    ].forEach((id) => {
      const el = $(id);
      if (el) el.value = "";
    });
    resetPasswordVisibility();
    syncPasswordToggleStates();
    void restoreBrowserSession();
  }, 50);
});

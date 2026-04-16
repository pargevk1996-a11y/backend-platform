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
  twoFactorEnabled: null,
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
    return "QR code created. Continue setup in the popup window.";
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
  const active = state.canManage2fa && hasActiveSession();
  const statusKnown = typeof state.twoFactorEnabled === "boolean";
  const canEnable = active && statusKnown && state.twoFactorEnabled === false;
  const canDisable = active && statusKnown && state.twoFactorEnabled === true;

  $("setup2faRow").classList.toggle("hidden", active ? !canEnable : false);
  $("disable2faSection").classList.toggle("hidden", !canDisable);

  $("setup2faBtn").disabled = !canEnable || state.loading;
  $("disable2faPassword").disabled = !canDisable || state.loading;
  $("disable2faCode").disabled = !canDisable || state.loading;
  $("disable2faBtn").disabled = !canDisable || state.loading;
  $("logoutBtn").disabled = !hasActiveSession() || state.loading;
  $("setupNote").textContent = !active
    ? "Sign in or create an account before managing 2FA."
    : !statusKnown
      ? "Loading 2FA status..."
      : canEnable
        ? "2FA is off for this account. Open setup, scan the QR, then confirm the authenticator code."
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

function defaultSetupWindowPlaceholder() {
  return "123456";
}

function setSetupWindowMessage(child, message, tone = "muted") {
  if (!child || child.closed) return;
  const input = child.document.getElementById("popupTotpCode");
  if (!input) return;
  input.placeholder = message || defaultSetupWindowPlaceholder();
  input.style.borderColor =
    tone === "error" ? "#ff6b6b" : tone === "success" ? "#6ee7a8" : "#2d3440";
}

function scheduleSetupWindowFit(child) {
  setTimeout(() => fitSetupWindow(child), 0);
  setTimeout(() => fitSetupWindow(child), 100);
}

function openSetupWindow() {
  const popupWidth = 400;
  const popupHeight = 470;
  const child = window.open(
    "",
    "backendPlatform2faSetup",
    `popup,width=${popupWidth},height=${popupHeight}`,
  );
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
  </head>
  <body style="margin:0"></body>
</html>`);
  child.document.close();

  const doc = child.document;
  const root = doc.documentElement;
  const body = doc.body;
  root.style.height = "100%";
  root.style.overflow = "hidden";
  body.style.height = "100%";
  body.style.margin = "0";
  body.style.overflow = "hidden";
  body.style.background = "#050505";
  body.style.color = "#f3f5f7";
  body.style.fontFamily = "system-ui,-apple-system,Segoe UI,sans-serif";

  const main = doc.createElement("main");
  main.id = "setupRoot";
  main.style.height = "100%";
  main.style.padding = "18px";
  main.style.display = "grid";
  main.style.overflow = "hidden";

  const stage = doc.createElement("div");
  stage.id = "setupStage";
  stage.style.minHeight = "0";
  stage.style.display = "grid";
  stage.style.placeItems = "center";
  stage.style.overflow = "hidden";

  const stack = doc.createElement("div");
  stack.id = "setupStack";
  stack.style.display = "grid";
  stack.style.justifyItems = "center";
  stack.style.alignContent = "center";
  stack.style.gap = "12px";
  stack.style.width = "220px";
  stack.style.maxWidth = "100%";

  const qrMount = doc.createElement("div");
  qrMount.id = "qrMount";
  qrMount.style.width = "100%";
  qrMount.style.display = "grid";
  qrMount.style.placeItems = "center";
  qrMount.style.overflow = "hidden";

  const qrFrame = doc.createElement("div");
  qrFrame.id = "setupQrFrame";
  qrFrame.style.boxSizing = "border-box";
  qrFrame.style.width = "220px";
  qrFrame.style.height = "220px";
  qrFrame.style.background = "transparent";
  qrFrame.style.display = "grid";
  qrFrame.style.placeItems = "center";
  qrFrame.style.overflow = "hidden";
  qrFrame.style.lineHeight = "0";

  qrMount.append(qrFrame);

  const inputWrap = doc.createElement("div");
  inputWrap.id = "setupCodeSection";
  inputWrap.style.width = "100%";

  const input = doc.createElement("input");
  input.id = "popupTotpCode";
  input.autocomplete = "off";
  input.inputMode = "numeric";
  input.maxLength = 8;
  input.setAttribute("aria-label", "Authenticator code");
  input.placeholder = "123456";
  input.style.width = "100%";
  input.style.minWidth = "0";
  input.style.height = "44px";
  input.style.padding = "10px 12px";
  input.style.border = "1px solid #2d3440";
  input.style.borderRadius = "10px";
  input.style.background = "#12161d";
  input.style.color = "#f3f5f7";
  input.style.font = "inherit";
  input.style.outline = "none";
  input.placeholder = defaultSetupWindowPlaceholder();

  inputWrap.append(input);
  stack.append(qrMount, inputWrap);
  stage.append(stack);
  main.append(stage);
  body.replaceChildren(main);

  try {
    child.resizeTo(popupWidth, popupHeight);
  } catch (_) {}
  child.addEventListener("resize", () => scheduleSetupWindowFit(child));
  scheduleSetupWindowFit(child);
  state.setupWindow = child;
  return child;
}

function fitSetupWindow(child) {
  if (!child || child.closed) return;
  const doc = child.document;
  const stage = doc.getElementById("setupStage");
  const stack = doc.getElementById("setupStack");
  const inputSection = doc.getElementById("setupCodeSection");
  const qrFrame = doc.getElementById("setupQrFrame");
  if (!stage || !stack || !inputSection || !qrFrame) return;

  const stageRect = stage.getBoundingClientRect();
  const stackGap = 12;
  const availableWidth = stageRect.width;
  const availableHeight = stageRect.height - inputSection.offsetHeight - stackGap;
  const qrSize = Math.max(150, Math.min(220, availableWidth, availableHeight));
  stack.style.width = `${Math.floor(qrSize)}px`;
  qrFrame.style.width = `${Math.floor(qrSize)}px`;
  qrFrame.style.height = `${Math.floor(qrSize)}px`;
}

function updateSetupWindowQr(child, qrBase64) {
  const qrFrame = child.document.getElementById("setupQrFrame");
  if (!qrFrame) return;
  qrFrame.innerHTML = `
    <img
      alt="Google Authenticator QR"
      src="data:image/png;base64,${qrBase64}"
      style="display:block;width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain;image-rendering:pixelated"
    />
  `;
  const input = child.document.getElementById("popupTotpCode");
  if (input) {
    input.disabled = false;
    input.value = "";
    input.placeholder = defaultSetupWindowPlaceholder();
    input.style.borderColor = "#2d3440";
    input.focus();
  }
  scheduleSetupWindowFit(child);
}

function updateSetupWindowResult(value, isError) {
  const child = state.setupWindow;
  if (!child || child.closed) return;
  const input = child.document.getElementById("popupTotpCode");
  if (input) {
    if (isError) {
      input.disabled = false;
      input.value = "";
      input.placeholder = "Wrong code";
      input.style.borderColor = "#ff6b6b";
      input.focus();
    } else {
      input.disabled = true;
      input.value = "";
      input.placeholder = "Enabled";
      input.style.borderColor = "#6ee7a8";
      setTimeout(() => {
        if (child.closed) return;
        child.close();
        if (state.setupWindow === child) state.setupWindow = null;
      }, 180);
      return;
    }
  }
  scheduleSetupWindowFit(child);
}

window.completeTwoFactorEnable = async (code) => {
  setLoading(true);
  setStatus("Enabling 2FA...", false);
  try {
    ensureSession();
    const totp = ensureTotp(code);
    const body = await post("/v1/two-factor/enable", { totp_code: totp }, { csrf: true });
    state.twoFactorEnabled = true;
    refreshTwoFactorState();
    setStatus("2FA enabled.", false);
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
    await syncSessionInfo();
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
      await syncSessionInfo();
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
    const input = child.document.getElementById("popupTotpCode");
    const submitPopupCode = () => {
      if (input.disabled) return;
      input.disabled = true;
      input.placeholder = "Checking...";
      input.style.borderColor = "#2d3440";
      window.completeTwoFactorEnable(input.value);
    };
    input.onkeydown = (event) => {
      if (event.key !== "Enter" || input.disabled) return;
      event.preventDefault();
      submitPopupCode();
    };
    input.oninput = () => {
      input.value = input.value.replace(/\D/g, "").slice(0, 8);
      setSetupWindowMessage(child, defaultSetupWindowPlaceholder());
    };
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
    state.twoFactorEnabled = false;
    refreshTwoFactorState();
    setStatus("2FA disabled.", false);
    setResult(body, false);
    $("disable2faPassword").value = "";
    $("disable2faCode").value = "";
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
bindEnter(["disable2faPassword", "disable2faCode"], "disable2faBtn");

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
    void restoreBrowserSession();
  }, 50);
});

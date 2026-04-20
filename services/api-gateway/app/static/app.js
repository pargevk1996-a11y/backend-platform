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
  challengeId: null,
  formMode: "register",
  /** @type {boolean | null} null = not loaded yet */
  twoFactorEnabled: null,
  /** After successful POST /v1/auth/password/forgot — unlock code + new password step */
  passwordResetCodeSent: false,
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

function apiErrorMessage(err) {
  if (err == null) return "Request failed.";
  if (typeof err === "string") return err;
  if (typeof err === "object") {
    return err.message || err.detail || err.error_code || "Request failed.";
  }
  return "Request failed.";
}

/** Deep-sanitize anything shown in the Response panel (no otpauth, secrets, raw QR, or token material). */
function sanitizeForPanel(value) {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") {
    if (value.startsWith("otpauth://")) return "[redacted: authenticator URI]";
    return value;
  }
  if (typeof value !== "object") return value;
  if (!Array.isArray(value) && value.requires_2fa === true) {
    return {
      message: "2FA required. Enter your 6-digit authenticator code in the form below.",
    };
  }
  if (Array.isArray(value)) return value.map(sanitizeForPanel);
  const out = {};
  for (const [key, val] of Object.entries(value)) {
    const k = key.toLowerCase();
    if (k === "access_token" || k === "refresh_token") {
      out[key] = "[redacted]";
      continue;
    }
    if (k === "challenge_id" || k === "challengeid") {
      out[key] = "[redacted]";
      continue;
    }
    if (k === "requires_2fa") {
      out[key] = "[redacted]";
      continue;
    }
    if (
      k === "qr_png_base64" ||
      k === "backup_codes" ||
      k.includes("otpauth") ||
      k === "secret" ||
      k === "totp_secret" ||
      k === "provisioning_uri" ||
      k === "manual_entry_key" ||
      k === "shared_secret"
    ) {
      out[key] = Array.isArray(val) ? `[redacted: ${val.length} items]` : "[redacted]";
      continue;
    }
    if (k === "tokens" && (val === null || val === undefined)) {
      out[key] = "[not issued]";
      continue;
    }
    if (k === "tokens" && val && typeof val === "object") {
      out[key] = sanitizeForPanel(val);
      continue;
    }
    out[key] = sanitizeForPanel(val);
    if (typeof out[key] === "string" && out[key].startsWith("otpauth://")) {
      out[key] = "[redacted: authenticator URI]";
    }
  }
  return out;
}

function setResult(value, isError) {
  const el = $("result");
  if (typeof value === "string") {
    el.textContent = value;
  } else {
    el.textContent = JSON.stringify(sanitizeForPanel(value), null, 2);
  }
  el.style.color = isError ? "var(--danger)" : "var(--text)";
}

function setLoading(isLoading) {
  state.loading = isLoading;
  ["login2faBtn", "sessionEnable2faBtn", "sessionDisable2faBtn", "registerEnable2faBtn", "logoutBtn"].forEach((id) => {
    const el = $(id);
    if (el) el.disabled = isLoading;
  });
  updateSessionChrome();
  refreshAccountState();
  syncResetPhaseControls();
}

function setTwoFaStep(visible) {
  $("twoFaStep").classList.toggle("hidden", !visible);
  state.needs2fa = visible;
}

function hasActiveSession() {
  return Boolean(state.tokens?.access_token && state.tokens?.refresh_token);
}

function formGuideText(mode) {
  if (hasActiveSession()) {
    return "Active session. Sign out before creating another account, signing in, or resetting a password.";
  }
  if (mode === "register") {
    return "Register: enter your email and password, then click \"Create account\".";
  }
  if (mode === "login") {
    return "Login: enter your email and password, then click \"Sign in\".";
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

function resetPasswordFlowUi() {
  state.passwordResetCodeSent = false;
  const p2 = $("resetPhase2");
  if (p2) p2.classList.add("hidden");
  const code = $("resetCode");
  const pw = $("resetPassword");
  const confirm = $("resetConfirmBtn");
  if (code) {
    code.value = "";
    code.disabled = true;
  }
  if (pw) {
    pw.value = "";
    pw.disabled = true;
  }
  if (confirm) confirm.disabled = true;
}

function syncResetPhaseControls() {
  const sent = state.passwordResetCodeSent;
  const code = $("resetCode");
  const pw = $("resetPassword");
  const confirm = $("resetConfirmBtn");
  const p2 = $("resetPhase2");
  if (p2) p2.classList.toggle("hidden", !sent);
  const locked = state.loading || !sent;
  if (code) code.disabled = locked;
  if (pw) pw.disabled = locked;
  if (confirm) confirm.disabled = locked;
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
  if (isReset) resetPasswordFlowUi();
  refreshAccountState();
  updateSessionChrome();
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

function wirePasswordToggles() {
  document.querySelectorAll(".password-toggle[data-password-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-password-target");
      const input = document.getElementById(id);
      if (!input) return;
      const showPlain = input.type === "password";
      input.type = showPlain ? "text" : "password";
      const hidden = !showPlain;
      btn.setAttribute("aria-label", hidden ? "Show password" : "Hide password");
      btn.setAttribute("title", hidden ? "Show password" : "Hide password");
      btn.setAttribute("aria-pressed", showPlain ? "true" : "false");
    });
  });
}

function openModal(backdropEl) {
  backdropEl.classList.remove("hidden");
  backdropEl.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeModal(backdropEl) {
  backdropEl.classList.add("hidden");
  backdropEl.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function wireModalDismiss(backdropEl, dialogSelector) {
  const dialog = backdropEl.querySelector(dialogSelector);
  backdropEl.addEventListener("click", (e) => {
    if (e.target === backdropEl) closeModal(backdropEl);
  });
  backdropEl.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => closeModal(backdropEl));
  });
  if (dialog) {
    dialog.addEventListener("click", (e) => e.stopPropagation());
  }
}

async function getJson(path, token) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(baseUrl() + path, { method: "GET", headers });
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

async function refreshTwoFactorStatus() {
  if (!hasActiveSession()) {
    state.twoFactorEnabled = null;
    updateSessionChrome();
    return;
  }
  const token = state.tokens?.access_token;
  if (!token) {
    state.twoFactorEnabled = null;
    updateSessionChrome();
    return;
  }
  try {
    const data = await getJson("/v1/sessions/me", token);
    state.twoFactorEnabled = Boolean(data.two_factor_enabled);
  } catch (_) {
    state.twoFactorEnabled = null;
  }
  updateSessionChrome();
}

function updateSessionChrome() {
  const layout = $("mainLayout");
  const sessionAside = $("sessionAside");
  const signedIn = hasActiveSession();
  const reg = state.formMode === "register";
  const en = state.twoFactorEnabled;
  const showSessionColumn = signedIn;
  const showRegisterEnable = signedIn && reg && en === false;
  const showSessionEnable = signedIn && !reg && en === false;
  const showDisable = signedIn && en === true;

  layout.classList.toggle("layout--guest", !showSessionColumn);
  sessionAside.classList.toggle("hidden", !showSessionColumn);

  const regRow = $("registerEnable2faRow");
  if (regRow) regRow.classList.toggle("hidden", !showRegisterEnable);
  $("sessionEnable2faBtn").classList.toggle("hidden", !showSessionEnable);
  $("sessionDisable2faBtn").classList.toggle("hidden", !showDisable);

  $("sessionEnable2faBtn").disabled = state.loading || en !== false;
  $("sessionDisable2faBtn").disabled = state.loading || en !== true;
  $("registerEnable2faBtn").disabled = state.loading || en !== false;
  $("logoutBtn").disabled = !state.tokens?.refresh_token || state.loading;
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
  void refreshTwoFactorStatus();
}

function clearSession() {
  setTokens(null);
  state.challengeId = null;
  state.twoFactorEnabled = null;
  setTwoFaStep(false);
  clearLoginTotpError();
  resetEnableModal();
  resetDisableModal();
  resetPasswordFlowUi();
  syncResetPhaseControls();
  updateSessionChrome();
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

const MODAL_ENABLE_TOTP_ERROR_TEXT = "Invalid 6-digit code";

function clearModalEnableTotpError() {
  const errEl = $("modalEnableTotpError");
  const inp = $("modalEnableTotp");
  if (errEl) {
    errEl.textContent = "";
    errEl.classList.add("hidden");
    errEl.setAttribute("aria-hidden", "true");
  }
  if (inp) inp.classList.remove("modal__totp-input--invalid");
}

function setModalEnableTotpError() {
  const errEl = $("modalEnableTotpError");
  const inp = $("modalEnableTotp");
  if (errEl) {
    errEl.textContent = MODAL_ENABLE_TOTP_ERROR_TEXT;
    errEl.classList.remove("hidden");
    errEl.setAttribute("aria-hidden", "false");
  }
  if (inp) inp.classList.add("modal__totp-input--invalid");
}

/** Wrong TOTP on POST /v1/two-factor/enable or POST /v1/auth/login/2fa. */
function isInvalidTwoFactorCodeResponse(err) {
  if (!err || typeof err !== "object") return false;
  const code = String(err.error_code || "").toUpperCase();
  if (err.status === 401 && code === "INVALID_2FA_CODE") return true;
  const msg = String(err.message || err.detail || "").toLowerCase();
  return err.status === 401 && msg.includes("invalid") && msg.includes("two-factor");
}

function isEnableModalTotpFailure(err) {
  return isInvalidTwoFactorCodeResponse(err);
}

const LOGIN_TOTP_ERROR_TEXT = MODAL_ENABLE_TOTP_ERROR_TEXT;

function clearLoginTotpError() {
  const errEl = $("loginTotpError");
  const inp = $("totpCode");
  if (errEl) {
    errEl.textContent = "";
    errEl.classList.add("hidden");
    errEl.setAttribute("aria-hidden", "true");
  }
  if (inp) inp.classList.remove("login-totp-input--invalid");
}

function setLoginTotpError() {
  const errEl = $("loginTotpError");
  const inp = $("totpCode");
  if (errEl) {
    errEl.textContent = LOGIN_TOTP_ERROR_TEXT;
    errEl.classList.remove("hidden");
    errEl.setAttribute("aria-hidden", "false");
  }
  if (inp) inp.classList.add("login-totp-input--invalid");
}

function safeLoginResultForPanel(body) {
  if (!body || typeof body !== "object") return body;
  if (body.requires_2fa) {
    return {
      message: "2FA required. Enter your 6-digit authenticator code in the form below.",
    };
  }
  return sanitizeForPanel(body);
}

function fillBackupCodeList(ul, codes) {
  if (!ul) return;
  ul.innerHTML = "";
  if (!Array.isArray(codes)) return;
  codes.forEach((c) => {
    const li = document.createElement("li");
    const code = document.createElement("code");
    code.textContent = c;
    code.className = "backup-code";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn--tiny btn--ghost";
    btn.textContent = "Copy";
    btn.addEventListener("click", () => {
      void navigator.clipboard.writeText(c).then(() => setStatus("Copied to clipboard.", false));
    });
    li.appendChild(code);
    li.appendChild(btn);
    ul.appendChild(li);
  });
}

function resetEnableModal() {
  $("modalQrImage").removeAttribute("src");
  $("modalEnableTotp").value = "";
  fillBackupCodeList($("modalBackupList"), []);
  clearModalEnableTotpError();
}

function resetDisableModal() {
  $("modalDisablePassword").value = "";
  $("modalDisableTotp").value = "";
}

async function startEnable2faFlow() {
  setLoading(true);
  setStatus("Preparing 2FA setup...", false);
  try {
    const token = ensureAccessToken();
    resetEnableModal();
    const body = await post("/v1/two-factor/setup", {}, token);
    if (!body.qr_png_base64) throw { message: "No QR in response" };
    $("modalQrImage").src = `data:image/png;base64,${body.qr_png_base64}`;
    $("modalQrImage").alt = "TOTP QR code";
    const codesOk = Array.isArray(body.backup_codes) && body.backup_codes.length === 10;
    fillBackupCodeList($("modalBackupList"), codesOk ? body.backup_codes : []);
    openModal($("enable2faModal"));
    if (!codesOk) {
      setStatus(
        "QR is ready, but backup codes are missing from the server response. Update auth-service, then try again.",
        true
      );
    } else {
      setStatus("Save backup codes, scan the QR, then confirm with your authenticator code.", false);
    }
    setResult({ status: "two_factor_setup", hint: "QR and backup codes are shown in the dialog only." }, false);
  } catch (err) {
    setStatus(apiErrorMessage(err) || "2FA setup failed.", true);
    setResult(sanitizeForPanel(err), true);
  } finally {
    setLoading(false);
  }
}

async function confirmEnable2faFromModal() {
  clearModalEnableTotpError();
  const totpRaw = ($("modalEnableTotp").value || "").trim();
  if (!/^[0-9]{6,8}$/.test(totpRaw)) {
    setModalEnableTotpError();
    return;
  }
  setLoading(true);
  setStatus("Enabling 2FA...", false);
  try {
    const token = ensureAccessToken();
    sync/local-main-2026-04-19
    await post("/v1/two-factor/enable", { totp_code: totpRaw }, token);
    const totp = ensureTotp($("modalEnableTotp").value);
    await post("/v1/two-factor/enable", { totp_code: totp }, token);
    main
    closeModal($("enable2faModal"));
    resetEnableModal();
    setStatus("Two-factor authentication is enabled.", false);
    setResult({ status: "two_factor_enabled" }, false);
    await refreshTwoFactorStatus();
  } catch (err) {
    if (isEnableModalTotpFailure(err)) {
      setModalEnableTotpError();
      setStatus("Ready.", false);
      return;
    }
    setStatus(apiErrorMessage(err) || "Enable 2FA failed.", true);
    setResult(sanitizeForPanel(err), true);
  } finally {
    setLoading(false);
  }
}

async function submitDisable2faFromModal() {
  setLoading(true);
  setStatus("Disabling 2FA...", false);
  try {
    const token = ensureAccessToken();
    const password = $("modalDisablePassword").value;
    if (!password) {
      setStatus("Password is required.", true);
      return;
    }
    const totpRaw = $("modalDisableTotp").value.trim();
    if (!totpRaw) {
      setStatus("Authenticator code is required.", true);
      return;
    }
    const payload = {
      password,
      totp_code: ensureTotp(totpRaw),
      backup_code: null,
    };
    const body = await post("/v1/two-factor/disable", payload, token);
    closeModal($("disable2faModal"));
    resetDisableModal();
    setStatus("Two-factor authentication disabled.", false);
    setResult(body, false);
    await refreshTwoFactorStatus();
  } catch (err) {
    setStatus(apiErrorMessage(err) || "Disable 2FA failed.", true);
    setResult(sanitizeForPanel(err), true);
  } finally {
    setLoading(false);
  }
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
    $("regPassword").value = "";
    setStatus("Account created.", false);
    setResult(body, false);
    await refreshTwoFactorStatus();
  } catch (err) {
    setStatus(apiErrorMessage(err) || "Registration failed.", true);
    setResult(sanitizeForPanel(err), true);
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
      setStatus("2FA required. Enter the code from your authenticator.", false);
      setTwoFaStep(true);
      clearLoginTotpError();
      await refreshTwoFactorStatus();
    } else {
      setStatus("Signed in.", false);
      setTwoFaStep(false);
      await refreshTwoFactorStatus();
    }
    setResult(safeLoginResultForPanel(body), false);
    $("loginPassword").value = "";
  } catch (err) {
    const code = String(err?.error_code || "").toUpperCase();
    if (code === "ACCOUNT_LOGIN_LOCKED") {
      setStatus(apiErrorMessage(err) || "Sign-in is blocked for this account.", true);
      setResult({ message: "Use password reset with your email to regain access." }, true);
    } else {
      setStatus(apiErrorMessage(err) || "Login failed.", true);
      setResult(sanitizeForPanel(err), true);
    }
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
    state.passwordResetCodeSent = true;
    syncResetPhaseControls();
    setStatus("If the email exists, a reset code was sent. Enter it below with a new password.", false);
    setResult(body, false);
  } catch (err) {
    const code = String(err?.error_code || "").toUpperCase();
    if (code === "RESET_FLOW_BLOCKED") {
      setStatus(apiErrorMessage(err) || "Password reset is not available.", true);
      setResult({ message: "Contact support using the email shown in the status message." }, true);
    } else {
      setStatus(apiErrorMessage(err) || "Reset request failed.", true);
      setResult(sanitizeForPanel(err), true);
    }
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
    resetPasswordFlowUi();
    syncResetPhaseControls();
  } catch (err) {
    const code = String(err?.error_code || "").toUpperCase();
    if (code === "RESET_FLOW_BLOCKED") {
      setStatus(apiErrorMessage(err) || "Password reset is not available.", true);
      setResult({ message: "Contact support using the email shown in the status message." }, true);
    } else {
      setStatus(apiErrorMessage(err) || "Password reset failed.", true);
      setResult(sanitizeForPanel(err), true);
    }
  } finally {
    setLoading(false);
  }
});

$("login2faBtn").addEventListener("click", async () => {
  clearLoginTotpError();
  const totpRaw = ($("totpCode").value || "").trim();
  if (!/^[0-9]{6}$/.test(totpRaw)) {
    setLoginTotpError();
    return;
  }
  setLoading(true);
  setStatus("Verifying 2FA...", false);
  setResult({ message: "Verifying 2FA…" }, false);
  try {
    const body = await post("/v1/auth/login/2fa", {
      challenge_id: state.challengeId,
      totp_code: totpRaw,
      backup_code: null,
    });
    handleTokens(body);
    setStatus("2FA verified.", false);
    setTwoFaStep(false);
    clearLoginTotpError();
    setResult(sanitizeForPanel(body), false);
    $("totpCode").value = "";
    state.challengeId = null;
    await refreshTwoFactorStatus();
  } catch (err) {
    if (isInvalidTwoFactorCodeResponse(err)) {
      setLoginTotpError();
      setStatus("Ready.", false);
      setResult({ message: "Correct the code below or start sign-in again from the beginning." }, false);
    } else {
      clearLoginTotpError();
      setStatus(apiErrorMessage(err) || "2FA verification failed.", true);
      setResult(sanitizeForPanel(err), true);
    }
  } finally {
    setLoading(false);
  }
});

$("totpCode").addEventListener("input", () => {
  if (!$("twoFaStep").classList.contains("hidden")) clearLoginTotpError();
});

$("sessionEnable2faBtn").addEventListener("click", () => void startEnable2faFlow());
$("registerEnable2faBtn").addEventListener("click", () => void startEnable2faFlow());

$("modalConfirmEnableBtn").addEventListener("click", () => void confirmEnable2faFromModal());
$("modalEnableTotp").addEventListener("input", () => {
  if (!$("enable2faModal").classList.contains("hidden")) clearModalEnableTotpError();
});

$("sessionDisable2faBtn").addEventListener("click", () => {
  resetDisableModal();
  openModal($("disable2faModal"));
});

$("modalDisableSubmitBtn").addEventListener("click", () => void submitDisable2faFromModal());

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
    setResult(sanitizeForPanel(err), true);
  } finally {
    setLoading(false);
  }
});

syncGatewayBaseUrlFromPage();
wirePasswordToggles();
setFormMode("register");
updateSessionChrome();

$("chooseRegister").addEventListener("click", () => setFormMode("register"));
$("chooseLogin").addEventListener("click", () => setFormMode("login"));
$("chooseReset").addEventListener("click", () => setFormMode("reset"));

bindEnter(["regEmail", "regPassword"], "regBtn", () => !$("formRegister").classList.contains("hidden"));
bindEnter(["loginEmail", "loginPassword"], "loginBtn", () => !$("formLogin").classList.contains("hidden"));
bindEnter(["resetEmail"], "resetRequestBtn", () => !$("formReset").classList.contains("hidden"));
bindEnter(["resetCode", "resetPassword"], "resetConfirmBtn", () => !$("formReset").classList.contains("hidden"));
bindEnter(["totpCode"], "login2faBtn", () => !$("twoFaStep").classList.contains("hidden"));
bindEnter(["modalEnableTotp"], "modalConfirmEnableBtn", () => !$("enable2faModal").classList.contains("hidden"));
bindEnter(["modalDisablePassword", "modalDisableTotp"], "modalDisableSubmitBtn", () => !$("disable2faModal").classList.contains("hidden"));

wireModalDismiss($("enable2faModal"), ".modal__dialog");
wireModalDismiss($("disable2faModal"), ".modal__dialog");

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("enable2faModal").classList.contains("hidden")) closeModal($("enable2faModal"));
  if (!$("disable2faModal").classList.contains("hidden")) closeModal($("disable2faModal"));
});

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
      "totpCode",
    ].forEach((id) => {
      const el = $(id);
      if (el) el.value = "";
    });
    state.challengeId = null;
    void restoreStoredSession();
  }, 50);
});

async function restoreStoredSession() {
  const stored = loadStoredTokens();
  if (!stored) {
    updateSessionChrome();
    refreshAccountState();
    return;
  }

  setTokens(stored);
  setTwoFaStep(false);
  setStatus("Restoring session...", false);
  setResult("Restoring session...", false);

  try {
    const body = await post("/v1/tokens/refresh", {
      refresh_token: stored.refresh_token,
    });
    handleTokens(body);
    setStatus("Session restored.", false);
    setResult({ status: "session_restored" }, false);
    await refreshTwoFactorStatus();
  } catch (err) {
    if ([400, 401, 403].includes(err.status)) {
      clearSession();
      setStatus("Session expired. Sign in again.", true);
    } else {
      setStatus("Session kept locally. Refresh failed.", true);
      await refreshTwoFactorStatus();
    }
    setResult(sanitizeForPanel(err), true);
  }
}

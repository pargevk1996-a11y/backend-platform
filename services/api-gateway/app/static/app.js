const $ = (id) => document.getElementById(id);
/** Legacy key — removed on load; cross-origin UI no longer persists tokens. */
const ACCESS_SESSION_STORAGE_KEY = "backend-platform.auth.access.v1";
const LEGACY_TOKEN_STORAGE_KEY = "backend-platform.auth.tokens.v1";
/** After a successful same-origin BFF login/refresh; lets reload tell "lost HttpOnly cookie" from "never signed in". */
const BROWSER_BFF_SESSION_HINT_KEY = "backend-platform.browser.had-bff-session.v1";
const SESSION_ACTION_IDS = [
  "login2faBtn",
  "sessionEnable2faBtn",
  "sessionDisable2faBtn",
  "registerEnable2faBtn",
  "logoutBtn",
];
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
  const raw = $("baseUrl").value.trim().replace(/\/+$/, "");
  if (raw) {
    return raw;
  }
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

/** Same-origin to API base → gateway browser BFF (HttpOnly refresh cookie). */
function useBrowserBff() {
  try {
    return new URL(baseUrl()).origin === window.location.origin;
  } catch {
    return false;
  }
}

/** Gateway URL must match this page — otherwise this UI must not store or send tokens in an insecure way. */
function isUnsafeCrossOriginGateway() {
  try {
    return new URL(baseUrl()).origin !== window.location.origin;
  } catch {
    /* Invalid URL while typing — do not lock the whole UI (that looked like "all buttons dead"). */
    return false;
  }
}

function syncUnsafeModeChrome() {
  const banner = $("unsafeGatewayBanner");
  const unsafe = isUnsafeCrossOriginGateway();
  if (banner) banner.classList.toggle("hidden", !unsafe);
  if (unsafe) {
    clearSession();
    migrateLegacyTokenStorage();
    try {
      sessionStorage.removeItem(ACCESS_SESSION_STORAGE_KEY);
    } catch (_) {
      /* ignore */
    }
    refreshAccountState();
    updateSessionChrome();
    return;
  }
  refreshAccountState();
  updateSessionChrome();
}

function migrateLegacyTokenStorage() {
  try {
    const legacy = localStorage.getItem(LEGACY_TOKEN_STORAGE_KEY);
    if (legacy) localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY);
  } catch (_) {
    // ignore
  }
}

function authRegisterPath() {
  return useBrowserBff() ? "/v1/browser-auth/register" : "/v1/auth/register";
}
function authLoginPath() {
  return useBrowserBff() ? "/v1/browser-auth/login" : "/v1/auth/login";
}
function authLogin2faPath() {
  return useBrowserBff() ? "/v1/browser-auth/login/2fa" : "/v1/auth/login/2fa";
}
function tokensRefreshPath() {
  return useBrowserBff() ? "/v1/browser-auth/refresh" : "/v1/tokens/refresh";
}
function tokensRevokePath() {
  return useBrowserBff() ? "/v1/browser-auth/revoke" : "/v1/tokens/revoke";
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
      message: "2FA required. Enter your 6-digit code.",
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
    if (k === "challenge_id" || k === "challengeid" || k === "requires_2fa") {
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
  return Boolean(state.tokens?.access_token);
}

function formGuideText(mode) {
  if (isUnsafeCrossOriginGateway()) {
    return 'Set Gateway URL to this page\'s origin (or leave empty for auto). This UI cannot safely manage tokens against a different origin.';
  }
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
  if (isUnsafeCrossOriginGateway()) {
    [...ACCOUNT_CONTROL_IDS, ...SESSION_ACTION_IDS].forEach((id) => {
      const el = $(id);
      if (el) el.disabled = true;
    });
    $("formGuide").textContent = formGuideText(state.formMode);
    return;
  }
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
  if (isUnsafeCrossOriginGateway()) {
    const code = $("resetCode");
    const pw = $("resetPassword");
    const confirm = $("resetConfirmBtn");
    if (code) code.disabled = true;
    if (pw) pw.disabled = true;
    if (confirm) confirm.disabled = true;
    return;
  }
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

function clearGuestFormFieldsForModeSwitch() {
  [
    "regEmail",
    "regPassword",
    "loginEmail",
    "loginPassword",
    "resetEmail",
    "resetCode",
    "resetPassword",
    "totpCode",
    "modalEnableTotp",
  ].forEach((id) => {
    const el = $(id);
    if (el) el.value = "";
  });
  clearLoginTotpError();
  clearModalEnableTotpError();
  resetDisableModal();
  state.challengeId = null;
  setTwoFaStep(false);
  setResult({ message: "Ready." }, false);
}

function setFormMode(mode) {
  state.formMode = mode;
  clearGuestFormFieldsForModeSwitch();
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
  else state.passwordResetCodeSent = false;
  syncResetPhaseControls();
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
  $("logoutBtn").disabled = !hasActiveSession() || state.loading;
  $("logoutBtn").classList.toggle("hidden", !signedIn);
}

async function post(path, payload, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const useCreds = path.startsWith("/v1/browser-auth");
  const res = await fetch(baseUrl() + path, {
    method: "POST",
    headers,
    body: JSON.stringify(payload ?? {}),
    credentials: useCreds ? "include" : "same-origin",
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
  if (isUnsafeCrossOriginGateway()) return;
  if (body.challenge_id) state.challengeId = body.challenge_id;
  const tokens = body.access_token ? body : body.tokens;
  if (!tokens?.access_token) return;
  if (useBrowserBff()) {
    try {
      sessionStorage.setItem(BROWSER_BFF_SESSION_HINT_KEY, "1");
    } catch (_) {
      /* ignore quota / private mode */
    }
    setTokens({ access_token: tokens.access_token, expires_in: tokens.expires_in });
  } else if (tokens.refresh_token) {
    setTokens({
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      expires_in: tokens.expires_in,
    });
  }
}

function loadStoredTokens() {
  migrateLegacyTokenStorage();
  if (useBrowserBff()) {
    try {
      sessionStorage.removeItem(ACCESS_SESSION_STORAGE_KEY);
    } catch (_) {
      /* ignore */
    }
    return null;
  }
  try {
    const raw = localStorage.getItem(LEGACY_TOKEN_STORAGE_KEY);
    if (!raw) return null;
    const tokens = JSON.parse(raw);
    if (tokens?.access_token && tokens?.refresh_token) return tokens;
  } catch (_) {
    // Ignore malformed local state and force a clean sign-in.
  }
  localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY);
  return null;
}

function saveTokens(tokens) {
  if (!tokens?.access_token) return;
  if (useBrowserBff()) {
    /* Memory-only: refresh via HttpOnly cookie on reload; avoids XSS reading sessionStorage. */
    return;
  }
  if (!tokens.refresh_token) return;
  localStorage.setItem(LEGACY_TOKEN_STORAGE_KEY, JSON.stringify(tokens));
}

function clearStoredTokens() {
  sessionStorage.removeItem(ACCESS_SESSION_STORAGE_KEY);
  localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY);
}

function setTokens(tokens) {
  if (tokens && isUnsafeCrossOriginGateway()) return;
  state.tokens = tokens;
  if (tokens) {
    saveTokens(tokens);
  } else {
    clearStoredTokens();
  }
  refreshAccountState();
  void refreshTwoFactorStatus();
}

/**
 * @param {{ keepBrowserBffHint?: boolean }} [opts]
 */
function clearSession(opts = {}) {
  const { keepBrowserBffHint = false } = opts;
  if (!keepBrowserBffHint) {
    try {
      sessionStorage.removeItem(BROWSER_BFF_SESSION_HINT_KEY);
    } catch (_) {
      /* ignore */
    }
  }
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

/** Revoke/refresh on HTTP+Secure cookie, or no cookie: server cannot revoke; sign-out is still valid locally. */
function isBenignSignOutNoRefreshCookieError(err) {
  if (!err || typeof err !== "object") return false;
  if (err.status !== 401) return false;
  const msg = String(err.message || err.detail || "").toLowerCase();
  return msg.includes("missing refresh") || msg.includes("refresh cookie");
}

/** Silent refresh failed before upstream: usually no HttpOnly cookie (e.g. Secure cookie rejected on HTTP). */
function isMissingRefreshCookieError(err) {
  return isBenignSignOutNoRefreshCookieError(err);
}

function isEnableModalTotpFailure(err) {
  return isInvalidTwoFactorCodeResponse(err);
}

function clearModalDisable2faError() {
  ["modalDisablePasswordError", "modalDisableTotpError"].forEach((id) => {
    const errEl = $(id);
    if (errEl) {
      errEl.textContent = "";
      errEl.classList.add("hidden");
      errEl.setAttribute("aria-hidden", "true");
    }
  });
  const pw = $("modalDisablePassword");
  const totp = $("modalDisableTotp");
  if (pw) pw.classList.remove("modal-disable-password--invalid");
  if (totp) totp.classList.remove("modal__totp-input--invalid");
}

/** Normalize thrown JSON from fetch (some proxies or older clients omit error_code). */
function normalizeGatewayError(err) {
  if (!err || typeof err !== "object") return err;
  const hasCode = Boolean(String(err.error_code || "").trim());
  if (hasCode) return err;
  const detail = err.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.error_code) {
    return {
      ...err,
      error_code: detail.error_code,
      message: detail.message ?? err.message,
      status: err.status,
    };
  }
  const detailStr = typeof detail === "string" ? detail : "";
  const msg = String(err.message ?? detailStr).toLowerCase();
  if (msg.includes("invalid") && (msg.includes("password") || msg.includes("email"))) {
    return { ...err, error_code: "INVALID_CREDENTIALS" };
  }
  if (msg.includes("invalid") && msg.includes("two-factor")) {
    return { ...err, error_code: "INVALID_2FA_CODE" };
  }
  return err;
}

/** Map auth-service errors to short copy for the disable-2FA dialog (not the main status line). */
function disableModalApiMessage(err) {
  if (!err || typeof err !== "object") return "Disable 2FA failed.";
  const code = String(err.error_code || "").toUpperCase();
  if (code === "INVALID_CREDENTIALS") return "Incorrect password.";
  if (code === "INVALID_2FA_CODE") return "Invalid authenticator code.";
  return apiErrorMessage(err) || "Disable 2FA failed.";
}

/**
 * @param {string} message
 * @param {"password" | "totp"} field
 */
function setModalDisable2faError(message, field) {
  clearModalDisable2faError();
  const pwEl = $("modalDisablePasswordError");
  const totpEl = $("modalDisableTotpError");
  const pw = $("modalDisablePassword");
  const totp = $("modalDisableTotp");
  if (field === "password" && pwEl) {
    pwEl.textContent = message;
    pwEl.classList.remove("hidden");
    pwEl.setAttribute("aria-hidden", "false");
    if (pw) pw.classList.add("modal-disable-password--invalid");
  } else if (field === "totp" && totpEl) {
    totpEl.textContent = message;
    totpEl.classList.remove("hidden");
    totpEl.setAttribute("aria-hidden", "false");
    if (totp) totp.classList.add("modal__totp-input--invalid");
  } else if (pwEl) {
    pwEl.textContent = message;
    pwEl.classList.remove("hidden");
    pwEl.setAttribute("aria-hidden", "false");
    if (pw) pw.classList.add("modal-disable-password--invalid");
  }
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
      message: "2FA required. Enter your 6-digit code.",
    };
  }
  return sanitizeForPanel(body);
}

/**
 * Copy text from a direct user gesture. Uses the Clipboard API when available; falls back to
 * execCommand so copy works on plain HTTP and older browsers.
 * @param {string} text
 * @returns {Promise<void>}
 */
function copyTextToClipboard(text) {
  return new Promise((resolve, reject) => {
    if (typeof navigator !== "undefined" && navigator.clipboard && window.isSecureContext) {
      navigator.clipboard
        .writeText(text)
        .then(() => resolve())
        .catch(() => {
          try {
            copyTextViaExecCommand(text);
            resolve();
          } catch (e) {
            reject(e);
          }
        });
      return;
    }
    try {
      copyTextViaExecCommand(text);
      resolve();
    } catch (e) {
      reject(e);
    }
  });
}

function copyTextViaExecCommand(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.setAttribute("aria-hidden", "true");
  ta.style.position = "fixed";
  ta.style.top = "0";
  ta.style.left = "0";
  ta.style.width = "1px";
  ta.style.height = "1px";
  ta.style.padding = "0";
  ta.style.border = "none";
  ta.style.outline = "none";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } finally {
    document.body.removeChild(ta);
  }
  if (!ok) {
    throw new Error("Copy command was rejected");
  }
}

function fillBackupCodeList(ul, codes) {
  const toolbar = $("modalBackupToolbar");
  if (toolbar) {
    toolbar.innerHTML = "";
    toolbar.classList.add("hidden");
  }
  if (!ul) return;
  ul.innerHTML = "";
  if (!Array.isArray(codes) || codes.length === 0) return;
  if (toolbar) {
    toolbar.classList.remove("hidden");
    const copyAllBtn = document.createElement("button");
    copyAllBtn.type = "button";
    copyAllBtn.className = "btn btn--tiny btn--ghost";
    copyAllBtn.textContent = "Copy all codes";
    copyAllBtn.addEventListener("click", () => {
      void copyTextToClipboard(codes.join("\n"))
        .then(() => setStatus("All backup codes copied to clipboard.", false))
        .catch(() =>
          setStatus(
            "Could not copy automatically. Select the codes in the list and copy manually (Ctrl/Cmd+C), or retype them into a password manager.",
            true
          )
        );
    });
    toolbar.appendChild(copyAllBtn);
  }
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
      void copyTextToClipboard(c)
        .then(() => setStatus("Backup code copied to clipboard.", false))
        .catch(() =>
          setStatus(
            "Could not copy automatically. Select the code and copy it manually (Ctrl/Cmd+C).",
            true
          )
        );
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
  clearModalDisable2faError();
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
    const totp = ensureTotp($("modalEnableTotp").value);
    await post("/v1/two-factor/enable", { totp_code: totp }, token);
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
  clearModalDisable2faError();
  setLoading(true);
  setStatus("Disabling 2FA...", false);
  try {
    const token = ensureAccessToken();
    const password = $("modalDisablePassword").value;
    if (!password) {
      setModalDisable2faError("Password is required.", "password");
      setStatus("Ready.", false);
      return;
    }
    const totpRaw = $("modalDisableTotp").value.trim();
    if (!totpRaw) {
      setModalDisable2faError("Authenticator code is required.", "totp");
      setStatus("Ready.", false);
      return;
    }
    if (!/^[0-9]{6,8}$/.test(totpRaw)) {
      setModalDisable2faError("Authenticator code must be 6–8 digits.", "totp");
      setStatus("Ready.", false);
      return;
    }
    const payload = {
      password,
      totp_code: totpRaw,
      backup_code: null,
    };
    const body = await post("/v1/two-factor/disable", payload, token);
    closeModal($("disable2faModal"));
    resetDisableModal();
    setStatus("Two-factor authentication disabled.", false);
    setResult(sanitizeForPanel(body), false);
    await refreshTwoFactorStatus();
  } catch (err) {
    const e = normalizeGatewayError(err);
    const code = String(e?.error_code || "").toUpperCase();
    const field = code === "INVALID_CREDENTIALS" ? "password" : code === "INVALID_2FA_CODE" ? "totp" : "password";
    setModalDisable2faError(disableModalApiMessage(e), field);
    setStatus("Ready.", false);
    setResult("", false);
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
    const body = await post(authRegisterPath(), {
      email: $("regEmail").value,
      password,
    });
    setTwoFaStep(false);
    $("regPassword").value = "";
    setStatus("Account created. Sign in with your email and password.", false);
    setResult(sanitizeForPanel(body), false);
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
    const body = await post(authLoginPath(), {
      email: $("loginEmail").value,
      password: $("loginPassword").value,
    });
    handleTokens(body);
    if (body.requires_2fa) {
      setStatus("2FA required. Enter your 6-digit code.", false);
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
    const forgotBody = await post("/v1/auth/password/forgot", { email });
    if (forgotBody && forgotBody.email_sent === false) {
      state.passwordResetCodeSent = false;
      syncResetPhaseControls();
      setStatus(
        "Reset email was not sent: outbound mail is not configured on the server. Ask an administrator to set SMTP (or deploy secrets).",
        true
      );
      setResult(forgotBody, true);
      return;
    }
    state.passwordResetCodeSent = true;
    syncResetPhaseControls();
    setStatus("If the email exists, a reset code was sent. Enter it below with a new password.", false);
    setResult(
      {
        message:
          "Request accepted. If this email is registered, check your inbox for a 6-digit code (and spam folder).",
      },
      false
    );
  } catch (err) {
    const code = String(err?.error_code || "").toUpperCase();
    if (code === "RESET_FLOW_BLOCKED") {
      setStatus(apiErrorMessage(err) || "Password reset is not available.", true);
      setResult({ message: apiErrorMessage(err) || "Password reset is not available for this account." }, true);
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
      setResult({ message: apiErrorMessage(err) || "Password reset is not available for this account." }, true);
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
    const body = await post(authLogin2faPath(), {
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
      setResult({ message: LOGIN_TOTP_ERROR_TEXT }, false);
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

$("modalDisablePassword")?.addEventListener("input", () => {
  if (!$("disable2faModal").classList.contains("hidden")) clearModalDisable2faError();
});
$("modalDisableTotp")?.addEventListener("input", () => {
  if (!$("disable2faModal").classList.contains("hidden")) clearModalDisable2faError();
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
    if (useBrowserBff()) {
      try {
        const body = await post(tokensRevokePath(), {});
        setStatus("Signed out.", false);
        setResult(sanitizeForPanel(body), false);
        return;
      } catch (err) {
        if (isBenignSignOutNoRefreshCookieError(err)) {
          setStatus("Signed out.", false);
          setResult({ message: "Signed out." }, false);
          return;
        }
        throw err;
      }
    }
    if (!refresh) {
      setStatus("No active session.", true);
      setResult({ status: "no_active_session" }, true);
      return;
    }
    const body = await post("/v1/tokens/revoke", { refresh_token: refresh });
    setStatus("Signed out.", false);
    setResult(sanitizeForPanel(body), false);
  } catch (err) {
    if (isBenignSignOutNoRefreshCookieError(err)) {
      setStatus("Signed out.", false);
      setResult({ message: "Signed out." }, false);
    } else {
      setStatus("Signed out locally. Server revoke failed.", true);
      setResult(sanitizeForPanel(err), true);
    }
  } finally {
    setLoading(false);
  }
});

syncGatewayBaseUrlFromPage();
$("baseUrl").addEventListener("input", () => syncUnsafeModeChrome());
$("baseUrl").addEventListener("change", () => {
  syncUnsafeModeChrome();
  if (!isUnsafeCrossOriginGateway()) {
    void restoreStoredSession();
  }
});
syncUnsafeModeChrome();
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
  migrateLegacyTokenStorage();

  if (isUnsafeCrossOriginGateway()) {
    clearSession();
    updateSessionChrome();
    refreshAccountState();
    return;
  }

  if (useBrowserBff()) {
    setTwoFaStep(false);
    setStatus("Restoring session...", false);
    setResult("Restoring session...", false);
    let hadBffSessionHint = false;
    try {
      hadBffSessionHint = sessionStorage.getItem(BROWSER_BFF_SESSION_HINT_KEY) === "1";
    } catch (_) {
      hadBffSessionHint = false;
    }
    try {
      const body = await post(tokensRefreshPath(), {});
      handleTokens(body);
      setStatus("Session restored.", false);
      setResult({ status: "session_restored" }, false);
      await refreshTwoFactorStatus();
    } catch (err) {
      clearSession({ keepBrowserBffHint: true });
      const st = err && typeof err === "object" ? err.status : undefined;
      if ([400, 401, 403].includes(st)) {
        if (isMissingRefreshCookieError(err)) {
          if (hadBffSessionHint) {
            setStatus(
              "No refresh cookie (session cannot resume after reload). Sign in again, or check Gateway URL / TLS proxy (TRUSTED_PROXY_IPS + X-Forwarded-Proto) — see README.",
              true,
            );
            setResult(
              {
                message: "Missing refresh cookie after reload.",
                typical_causes: [
                  "Browser did not store or send HttpOnly cookie bp_rt (wrong page origin vs Gateway URL, or Set-Cookie dropped: Secure on plain HTTP, blocked third-party, etc.).",
                  "HTTPS behind a proxy: TRUSTED_PROXY_IPS must include the proxy; X-Forwarded-For and X-Forwarded-Proto must reflect the browser (see gateway docs).",
                  "Override: set REFRESH_COOKIE_SECURE=false in api-gateway .env only if you must force non-Secure cookie on HTTP.",
                ],
              },
              false,
            );
          } else {
            setStatus("Ready.", false);
            setResult({ message: "No active session. Sign in to continue." }, false);
          }
        } else {
          setStatus("Ready.", false);
          setResult({ message: "No active session. Sign in to continue." }, false);
        }
      } else {
        setStatus("Could not restore session (refresh failed).", true);
        setResult(sanitizeForPanel(err), true);
      }
    }
    return;
  }

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

const $ = (id) => document.getElementById(id);

const state = {
  tokens: null,
  loading: false,
  needs2fa: false,
  canSetup2fa: false,
  challengeId: null,
};

function baseUrl() {
  return $("baseUrl").value.replace(/\/+$/, "");
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
    "regBtn",
    "loginBtn",
    "login2faBtn",
    "setup2faBtn",
    "enable2faBtn",
    "logoutBtn",
    "resetRequestBtn",
    "resetConfirmBtn",
  ].forEach((id) => {
    const el = $(id);
    if (el) el.disabled = isLoading;
  });
}

function setTwoFaStep(visible) {
  $("twoFaStep").classList.toggle("hidden", !visible);
  state.needs2fa = visible;
}

function setSetupEnabled(enabled) {
  state.canSetup2fa = enabled;
  $("setup2faBtn").disabled = !enabled || state.loading;
}

function setFormMode(mode) {
  const isRegister = mode === "register";
  const isLogin = mode === "login";
  const isReset = mode === "reset";
  $("formRegister").classList.toggle("hidden", !isRegister);
  $("formLogin").classList.toggle("hidden", !isLogin);
  $("formReset").classList.toggle("hidden", !isReset);
  $("chooseRegister").classList.toggle("active", isRegister);
  $("chooseLogin").classList.toggle("active", isLogin);
  $("chooseReset").classList.toggle("active", isReset);
  $("formGuide").textContent = isRegister
    ? "Register: enter your email and password, then click \"Create account\". After that you can create a QR once and enable 2FA."
    : isLogin
      ? "Login: enter your email and password, then click \"Sign in\". If 2FA is required, the step will appear below — enter the Google Authenticator code."
      : "Reset password: request a 6-digit code by email, then enter the code and a new password.";
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
  $("qrImage").classList.remove("visible");
  $("qrImage").removeAttribute("src");
  $("qrEmpty").classList.remove("hidden");
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
  if (!res.ok) throw body;
  return body;
}

function handleTokens(body) {
  if (body.challenge_id) state.challengeId = body.challenge_id;
  if (body.access_token) state.tokens = body;
  if (body.tokens) state.tokens = body.tokens;
}

function redactTokens(payload) {
  const clone = JSON.parse(JSON.stringify(payload));
  if (clone.access_token) clone.access_token = "[redacted]";
  if (clone.refresh_token) clone.refresh_token = "[redacted]";
  if (clone.tokens?.access_token) clone.tokens.access_token = "[redacted]";
  if (clone.tokens?.refresh_token) clone.tokens.refresh_token = "[redacted]";
  if (clone.backup_codes) clone.backup_codes = "[redacted]";
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
    } else {
      setStatus("Signed in.", false);
      setTwoFaStep(false);
    }
    setSetupEnabled(false);
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
      setStatus("QR can be created only right after registration.", true);
      return;
    }
    const token = ensureAccessToken();
    const body = await post("/v1/two-factor/setup", {}, token);
    if (body.qr_png_base64) {
      $("qrImage").src = `data:image/png;base64,${body.qr_png_base64}`;
      $("qrImage").classList.add("visible");
      $("qrEmpty").classList.add("hidden");
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
  try {
    const refresh = state.tokens?.refresh_token;
    if (!refresh) {
      setStatus("No active session.", true);
      return;
    }
    const body = await post("/v1/tokens/revoke", { refresh_token: refresh });
    state.tokens = null;
    resetQr();
    setStatus("Signed out.", false);
    setResult(body, false);
    setSetupEnabled(false);
  } catch (err) {
    setStatus(err.message || "Sign out failed.", true);
    setResult(err, true);
  } finally {
    setLoading(false);
  }
});

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
  }, 50);
});

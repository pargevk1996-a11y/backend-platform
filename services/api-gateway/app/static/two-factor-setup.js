const $ = (id) => document.getElementById(id);

const MAIN_SOURCE = "backend-platform:2fa-setup:main";
const POPUP_SOURCE = "backend-platform:2fa-setup:popup";

const params = new URLSearchParams(window.location.search);
const openerOrigin = params.get("openerOrigin") || window.location.origin;

const state = {
  enabled: false,
  qrReady: false,
  submitting: false,
};

function postToOpener(type, payload = {}) {
  if (!window.opener || window.opener.closed) return;
  window.opener.postMessage(
    {
      source: POPUP_SOURCE,
      type,
      payload,
    },
    openerOrigin,
  );
}

function setStatus(message, tone = "muted") {
  const status = $("setupStatus");
  status.textContent = message;
  status.dataset.tone = tone;
}

function resetSetupView(message = "Waiting for secure setup data...") {
  state.enabled = false;
  state.qrReady = false;
  state.submitting = false;
  $("qrImage").removeAttribute("src");
  $("qrImage").hidden = true;
  $("qrPlaceholder").hidden = false;
  $("qrFrame").setAttribute("aria-busy", "true");
  $("manualSection").hidden = true;
  $("manualEntryKey").textContent = "";
  $("totpCode").value = "";
  $("totpCode").disabled = true;
  $("submitBtn").disabled = true;
  $("submitBtn").textContent = "Enable 2FA";
  setStatus(message, "muted");
}

function setSubmitting(submitting) {
  state.submitting = submitting;
  $("totpCode").disabled = submitting || !state.qrReady || state.enabled;
  $("submitBtn").disabled = submitting || !state.qrReady || state.enabled || $("totpCode").value.length < 6;
  $("submitBtn").textContent = submitting ? "Checking..." : "Enable 2FA";
}

function showManualEntryKey(manualEntryKey) {
  const key = String(manualEntryKey || "").trim();
  const section = $("manualSection");
  if (!key) {
    section.hidden = true;
    $("manualEntryKey").textContent = "";
    return;
  }
  $("manualEntryKey").textContent = key;
  section.hidden = false;
}

function showQr(qrPngBase64, manualEntryKey) {
  state.qrReady = true;
  $("qrImage").src = `data:image/png;base64,${qrPngBase64}`;
  $("qrImage").hidden = false;
  $("qrPlaceholder").hidden = true;
  $("qrFrame").setAttribute("aria-busy", "false");
  showManualEntryKey(manualEntryKey);
  $("totpCode").disabled = false;
  $("submitBtn").disabled = true;
  setStatus("Scan the QR or use the manual key, then enter the 6-8 digit code.", "muted");
  $("totpCode").focus();
}

function showError(message) {
  setStatus(message || "Setup failed. Try again from the main window.", "error");
  if (!state.enabled && state.qrReady) {
    $("totpCode").value = "";
    setSubmitting(false);
    $("totpCode").focus();
  }
}

function closeAfterSuccess(message) {
  resetSetupView();
  state.enabled = true;
  setStatus(message || "2FA enabled. Closing setup...", "success");
  setSubmitting(true);
  setTimeout(() => window.close(), 250);
}

function normalizeCodeInput() {
  const input = $("totpCode");
  input.value = input.value.replace(/\D/g, "").slice(0, 8);
  $("submitBtn").disabled = state.submitting || !state.qrReady || state.enabled || input.value.length < 6;
}

window.addEventListener("message", (event) => {
  const data = event.data;
  if (event.origin !== openerOrigin) return;
  if (!data || typeof data !== "object" || data.source !== MAIN_SOURCE) return;

  if (data.type === "loading") {
    resetSetupView(data.payload?.message || "Generating QR code...");
    setSubmitting(false);
    return;
  }

  if (data.type === "qr") {
    showQr(data.payload?.qrPngBase64 || "", data.payload?.manualEntryKey || "");
    return;
  }

  if (data.type === "submitting") {
    setStatus(data.payload?.message || "Checking authenticator code...", "muted");
    setSubmitting(true);
    return;
  }

  if (data.type === "enabled") {
    closeAfterSuccess(data.payload?.message);
    return;
  }

  if (data.type === "error") {
    showError(data.payload?.message);
  }
});

$("totpCode").addEventListener("input", normalizeCodeInput);

$("codeForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const code = $("totpCode").value.trim();
  if (!/^[0-9]{6,8}$/.test(code)) {
    showError("Enter the 6-8 digit code from your authenticator app.");
    return;
  }
  setSubmitting(true);
  postToOpener("submit", { code });
});

window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  resetSetupView("Waiting for a fresh secure setup...");
  postToOpener("ready");
});

resetSetupView();
postToOpener("ready");

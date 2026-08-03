// Handles sign-in validation, captcha checks, and hold-to-reveal password input.
// Load authentication separately so captcha generation always initializes.
const authenticationModule = import("./auth.js?v=signin-captcha-1");

// DOM references for the sign-in form and its interactive controls.
const loginForm = document.getElementById("loginForm");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const submitButton = document.getElementById("loginButton");
const loginStatus = document.getElementById("loginStatus");
const captchaChallenge = document.getElementById("captchaChallenge");
const captchaInput = document.getElementById("captchaInput");
const captchaRefresh = document.getElementById("captchaRefresh");
const passwordToggleButtons = document.querySelectorAll("[data-password-toggle]");

let captchaAnswer = null;
const captchaCharacters = "abcdefghijkmnpqrstuvwxyz";
const captchaLength = 5;

// Shows validation, success, and service messages under the form.
function setStatus(message, isError = false) {
  if (!loginStatus) return;
  loginStatus.textContent = message;
  loginStatus.classList.toggle("error-message", isError);
}

// Prevents double submits while the sign-in request is running.
function setSubmitting(isSubmitting) {
  if (!submitButton) return;
  submitButton.disabled = isSubmitting;
  submitButton.textContent = isSubmitting ? "Signing in…" : "Sign in";
}

function randomCaptchaCharacter() {
  const index = Math.floor(Math.random() * captchaCharacters.length);
  return captchaCharacters[index];
}

// Creates a new random text captcha and clears the user's previous answer.
function generateCaptcha() {
  captchaAnswer = Array.from(
    { length: captchaLength },
    randomCaptchaCharacter
  ).join("");
  window.GBTAC_CAPTCHA_ANSWER = captchaAnswer;

  if (captchaChallenge) {
    captchaChallenge.textContent = captchaAnswer;
  }

  if (captchaInput) {
    captchaInput.value = "";
    captchaInput.setAttribute("aria-invalid", "false");
  }
}

function isCaptchaValid() {
  const expectedAnswer = captchaAnswer || window.GBTAC_CAPTCHA_ANSWER;
  if (!captchaInput || !expectedAnswer) return true;

  const enteredValue = captchaInput.value.trim().toLowerCase();
  return enteredValue !== "" && enteredValue === expectedAnswer;
}

// Finds which password input belongs to the clicked eye icon.
function getPasswordToggleTarget(button) {
  return document.getElementById(button.dataset.target);
}

// Password is visible only while the user is holding the eye icon.
function revealPassword(button) {
  const targetInput = getPasswordToggleTarget(button);
  if (!targetInput) return;

  targetInput.type = "text";
  button.setAttribute("aria-label", "Password visible while pressed");
  button.setAttribute("aria-pressed", "true");
}

// Hides the password again when the press ends or focus leaves the icon.
function hidePassword(button) {
  const targetInput = getPasswordToggleTarget(button);
  if (!targetInput) return;

  targetInput.type = "password";
  button.setAttribute("aria-label", "Show password");
  button.setAttribute("aria-pressed", "false");
}

function hideAllPasswords() {
  passwordToggleButtons.forEach(hidePassword);
}

// Mouse, touch, and keyboard controls all use the same hold-to-reveal behavior.
passwordToggleButtons.forEach((button) => {
  button.setAttribute("aria-pressed", "false");

  button.addEventListener("pointerdown", (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    event.preventDefault();
    revealPassword(button);
  });

  button.addEventListener("pointerup", () => hidePassword(button));
  button.addEventListener("pointerleave", () => hidePassword(button));
  button.addEventListener("pointercancel", () => hidePassword(button));
  button.addEventListener("blur", () => hidePassword(button));
  button.addEventListener("contextmenu", (event) => event.preventDefault());
  button.addEventListener("click", (event) => event.preventDefault());

  button.addEventListener("keydown", (event) => {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    if (!event.repeat) {
      revealPassword(button);
    }
  });

  button.addEventListener("keyup", (event) => {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    hidePassword(button);
  });
});

// Safety net: always hide passwords if the user releases outside the icon.
document.addEventListener("pointerup", hideAllPasswords);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    hideAllPasswords();
  }
});

captchaRefresh?.addEventListener("click", () => {
  setStatus("");
  generateCaptcha();
  captchaInput?.focus();
});

// Start with a captcha ready for the first sign-in attempt.
generateCaptcha();

// Checks the captcha first, then submits the sign-in form.
loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("");

  if (!isCaptchaValid()) {
    setStatus("Enter the correct captcha answer.", true);
    generateCaptcha();
    captchaInput?.setAttribute("aria-invalid", "true");
    captchaInput?.focus();
    return;
  }

  setSubmitting(true);

  try {
    const { signIn } = await authenticationModule;
    const user = await signIn(emailInput.value, passwordInput.value);
    setStatus(`Signed in as ${user.name}. Redirecting…`);
    window.location.replace("dashboard.html");
  } catch (error) {
    setStatus(error.message || "Sign-in failed.", true);
    passwordInput.value = "";
    generateCaptcha();
    passwordInput.focus();
  } finally {
    setSubmitting(false);
  }
});

// Already signed-in users should not stay on the sign-in page.
async function redirectExistingSession() {
  try {
    const { getCurrentUser } = await authenticationModule;
    const user = await getCurrentUser();
    if (user) {
      window.location.replace("dashboard.html");
    }
  } catch (error) {
    if (error.status !== 401) {
      setStatus("The authentication service is temporarily unavailable.", true);
    }
  }
}

redirectExistingSession();

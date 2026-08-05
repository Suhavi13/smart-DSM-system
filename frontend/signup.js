// Handles signup validation, password checklist updates, and account creation.
import { getCurrentUser, signUp } from "./auth.js";

// DOM references for the signup form and password checklist.
const signupForm = document.getElementById("signupForm");
const nameInput = document.getElementById("displayName");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const confirmPasswordInput = document.getElementById("confirmPassword");
const submitButton = document.getElementById("signupButton");
const signupStatus = document.getElementById("signupStatus");
const passwordRequirementItems = document.querySelectorAll(
  "[data-password-rule]"
);
const passwordToggleButtons = document.querySelectorAll("[data-password-toggle]");
const uppercasePattern = /[A-Z]/;
const lowercasePattern = /[a-z]/;
const numberPattern = /\d/;
const specialCharacterPattern = /[^A-Za-z0-9\s]/;
const spacePattern = /\s/;

// Shows validation, success, and service messages under the form.
function setStatus(message, isError = false) {
  if (!signupStatus) return;
  signupStatus.textContent = message;
  signupStatus.classList.toggle("error-message", isError);
}

// Prevents double submits while account creation is running.
function setSubmitting(isSubmitting) {
  if (!submitButton) return;
  submitButton.disabled = isSubmitting;
  submitButton.textContent = isSubmitting
    ? "Creating account…"
    : "Create Viewer account";
}

// Evaluates every password rule used by the visible checklist.
function getPasswordRequirementState() {
  const password = passwordInput?.value || "";
  const confirmation = confirmPasswordInput?.value || "";

  return {
    length: password.length >= 8,
    uppercase: uppercasePattern.test(password),
    lowercase: lowercasePattern.test(password),
    number: numberPattern.test(password),
    special: specialCharacterPattern.test(password),
    spaces: password.length > 0 && !spacePattern.test(password),
    match:
      password.length > 0 &&
      confirmation.length > 0 &&
      password === confirmation,
  };
}

// Updates checklist styling and input accessibility state as the user types.
function updatePasswordRequirements() {
  const state = getPasswordRequirementState();
  const hasPassword = Boolean(passwordInput?.value);
  const hasConfirmation = Boolean(confirmPasswordInput?.value);

  passwordRequirementItems.forEach((item) => {
    const rule = item.dataset.passwordRule;
    const isValid = Boolean(state[rule]);

    item.classList.toggle("is-valid", isValid);
  });

  if (passwordInput) {
    passwordInput.setAttribute(
      "aria-invalid",
      String(hasPassword && !arePasswordRulesSatisfied(state))
    );
  }

  if (confirmPasswordInput) {
    confirmPasswordInput.setAttribute(
      "aria-invalid",
      String(hasConfirmation && !state.match)
    );
  }

  return state;
}

// Keeps the submit handler readable by grouping the required password checks.
function arePasswordRulesSatisfied(state) {
  return (
    state.length &&
    state.uppercase &&
    state.lowercase &&
    state.number &&
    state.special &&
    state.spaces
  );
}

// Moves focus to the field that needs attention before submitting.
function focusPasswordRequirementError(state) {
  if (!arePasswordRulesSatisfied(state)) {
    setStatus(
      "Password must meet every listed requirement.",
      true
    );
    passwordInput.focus();
    return true;
  }

  if (!state.match) {
    setStatus("Passwords do not match.", true);
    confirmPasswordInput.focus();
    return true;
  }

  return false;
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

passwordInput?.addEventListener("input", updatePasswordRequirements);
confirmPasswordInput?.addEventListener("input", updatePasswordRequirements);
updatePasswordRequirements();

// Validates the visible checklist before requesting account creation.
signupForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("");

  const passwordState = updatePasswordRequirements();
  if (focusPasswordRequirementError(passwordState)) {
    return;
  }

  setSubmitting(true);

  try {
    const user = await signUp(
      nameInput.value,
      emailInput.value,
      passwordInput.value
    );
    setStatus(`Viewer account created for ${user.name}. Redirecting…`);
    window.location.replace("dashboard.html");
  } catch (error) {
    setStatus(error.message || "Account creation failed.", true);
  } finally {
    setSubmitting(false);
  }
});

// Already signed-in users should not stay on the signup page.
async function redirectExistingSession() {
  try {
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

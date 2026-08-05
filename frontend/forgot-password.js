import { requestPasswordReset } from "./auth.js";

const form = document.getElementById("forgotPasswordForm");
const emailInput = document.getElementById("email");
const submitButton = document.getElementById("resetButton");
const statusMessage = document.getElementById("resetStatus");

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error-message", isError);
}

function setSubmitting(isSubmitting) {
  submitButton.disabled = isSubmitting;
  submitButton.textContent = isSubmitting ? "Sending…" : "Send reset email";
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("");
  setSubmitting(true);

  try {
    await requestPasswordReset(emailInput.value);
    setStatus(
      "If an account exists for that email, Firebase will send password-reset instructions."
    );
  } catch (error) {
    setStatus(error.message || "Unable to send the reset email.", true);
  } finally {
    setSubmitting(false);
  }
});

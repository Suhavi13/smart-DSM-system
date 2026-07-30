import {
  getCurrentUser,
  initializeAuthentication,
  msalApp,
  signIn,
  signOut,
} from "./auth.js";


const signInButton = document.getElementById("microsoftSignInButton");
const signOutButton = document.getElementById("microsoftSignOutButton");
const loginStatus = document.getElementById("loginStatus");


function setStatus(message, isError = false) {
  if (!loginStatus) {
    return;
  }

  loginStatus.textContent = message;
  loginStatus.classList.toggle("error-message", isError);
}


signInButton?.addEventListener("click", () => {
  signIn().catch((error) => {
    console.error("Microsoft sign-in failed:", error);
    setStatus(error.message || "Microsoft sign-in failed.", true);
  });
});


signOutButton?.addEventListener("click", () => {
  signOut().catch((error) => {
    console.error("Microsoft sign-out failed:", error);
  });
});


async function initializeLoginPage() {
  try {
    await initializeAuthentication();

    if (!msalApp.getActiveAccount()) {
      setStatus("Use your assigned Microsoft account to continue.");
      return;
    }

    setStatus("Checking your dashboard role…");
    const user = await getCurrentUser();
    setStatus(`Signed in as ${user.name}. Redirecting…`);
    window.location.replace("dashboard.html");
  } catch (error) {
    console.error("Authentication check failed:", error);
    setStatus(error.message || "Your account does not have dashboard access.", true);

    if (signOutButton) {
      signOutButton.hidden = false;
    }
  }
}

initializeLoginPage();

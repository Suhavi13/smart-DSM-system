import {
  requireSignedInUser,
  signOut,
} from "./auth.js";


function applyRoleVisibility(user) {
  document.querySelectorAll("[data-operator-only]").forEach((element) => {
    element.hidden = !user.isOperator;
  });

  document.querySelectorAll("[data-viewer-only]").forEach((element) => {
    element.hidden = user.isOperator;
  });
}


function renderUser(user) {
  document.querySelectorAll("[data-auth-user-name]").forEach((element) => {
    element.textContent = user.name;
  });

  document.querySelectorAll("[data-auth-user-role]").forEach((element) => {
    element.textContent = user.isOperator ? "Operator" : "Viewer";
  });

  applyRoleVisibility(user);
}


function renderAuthenticationError(error) {
  const message = error?.message || "Authentication failed.";
  const main = document.querySelector("main");

  if (main) {
    main.innerHTML = `
      <section class="auth-access-error" role="alert">
        <h1>Dashboard access unavailable</h1>
        <p>${message}</p>
        <button type="button" class="btn btn-secondary" data-sign-out>
          Sign out
        </button>
      </section>
    `;
  }
}


async function initializeProtectedPage() {
  try {
    const user = await requireSignedInUser();
    if (!user) {
      return;
    }

    window.APP_USER = user;
    renderUser(user);

    document.dispatchEvent(
      new CustomEvent("authentication:ready", { detail: user })
    );
  } catch (error) {
    console.error("Microsoft Entra authentication failed:", error);
    renderAuthenticationError(error);
  }
}


document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-sign-out]");
  if (button) {
    signOut().catch((error) => {
      console.error("Sign-out failed:", error);
    });
  }
});


document.addEventListener("recommendations:rendered", () => {
  if (window.APP_USER) {
    applyRoleVisibility(window.APP_USER);
  }
});

initializeProtectedPage();

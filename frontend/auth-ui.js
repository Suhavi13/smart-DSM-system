// Applies signed-in user details and role-based visibility to protected pages.
import { requireSignedInUser, signOut } from "./auth.js";

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
  const main = document.querySelector("main");
  if (!main) return;

  const section = document.createElement("section");
  section.className = "auth-access-error";
  section.setAttribute("role", "alert");

  const heading = document.createElement("h1");
  heading.textContent = "Dashboard access unavailable";

  const message = document.createElement("p");
  message.textContent = error?.message || "Authentication failed.";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-secondary";
  button.dataset.signOut = "";
  button.textContent = "Return to sign in";

  section.append(heading, message, button);
  main.replaceChildren(section);
}

function confirmSignOut() {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "app-dialog-overlay";
    overlay.innerHTML = `
      <section
        class="app-dialog app-dialog-reject"
        role="alertdialog"
        aria-modal="true"
        aria-label="Logout confirmation"
        aria-describedby="signOutDialogMessage"
      >
        <p id="signOutDialogMessage">Are you sure you want to log out?</p>
        <div class="app-dialog-actions">
          <button type="button" class="btn app-dialog-confirm">Yes</button>
          <button type="button" class="btn app-dialog-cancel">No</button>
        </div>
      </section>
    `;

    const confirmButton = overlay.querySelector(".app-dialog-confirm");
    const cancelButton = overlay.querySelector(".app-dialog-cancel");

    const closeDialog = (confirmed) => {
      document.removeEventListener("keydown", handleKeydown);
      overlay.remove();
      resolve(confirmed);
    };

    const handleKeydown = (event) => {
      if (event.key === "Escape") {
        closeDialog(false);
      }
    };

    confirmButton.addEventListener("click", () => closeDialog(true));
    cancelButton.addEventListener("click", () => closeDialog(false));
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) {
        closeDialog(false);
      }
    });
    document.addEventListener("keydown", handleKeydown);
    document.body.append(overlay);
    cancelButton.focus();
  });
}

async function initializeProtectedPage() {
  try {
    const user = await requireSignedInUser();
    if (!user) return;

    const requiredRole = document.body?.dataset.requiredRole;
    if (requiredRole === "Operator" && !user.isOperator) {
      window.location.replace("dashboard.html?access=viewer");
      return;
    }

    window.APP_USER = user;
    renderUser(user);
    document.dispatchEvent(
      new CustomEvent("authentication:ready", { detail: user })
    );
  } catch (error) {
    console.error("Authentication failed:", error);
    renderAuthenticationError(error);
  }
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-sign-out]");
  if (button) {
    event.preventDefault();

    if (!await confirmSignOut()) {
      return;
    }

    signOut().catch((error) => console.error("Sign-out failed:", error));
  }
});

document.addEventListener("recommendations:rendered", () => {
  if (window.APP_USER) {
    applyRoleVisibility(window.APP_USER);
  }
});

initializeProtectedPage();

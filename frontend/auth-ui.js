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

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-sign-out]");
  if (button) {
    event.preventDefault();
    signOut().catch((error) => console.error("Sign-out failed:", error));
  }
});

document.addEventListener("recommendations:rendered", () => {
  if (window.APP_USER) {
    applyRoleVisibility(window.APP_USER);
  }
});

initializeProtectedPage();

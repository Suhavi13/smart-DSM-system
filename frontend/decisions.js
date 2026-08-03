// Saves Operator approve/reject decisions for recommendation cards.
import { apiRequest } from "./api.js";

(() => {
  "use strict";

  // Creates a unique key so repeated clicks do not save duplicate decisions.
  function createIdempotencyKey() {
    if (
      window.crypto &&
      typeof window.crypto.randomUUID === "function"
    ) {
      return window.crypto.randomUUID();
    }

    return (
      Date.now().toString(36) +
      "-" +
      Math.random().toString(36).slice(2)
    );
  }

  // Captures the visible recommendation text before an approve/reject decision.
  function getCardSnapshot(card) {
    const title =
      card.querySelector(".recommendation-title, h2, h3")
        ?.textContent.trim() || "Untitled recommendation";
    const description =
      card.querySelector(".recommendation-description")
        ?.textContent.trim() || "";
    const reason =
      card.querySelector(".recommendation-reason")
        ?.textContent.trim() || "";
    const priority =
      card.querySelector(".priority")?.textContent.trim() || "";
    const evidence = [...card.querySelectorAll(
      ".recommendation-evidence-item"
    )].map((item) => item.textContent.replace(/\s+/g, " ").trim());

    return { title, description, reason, priority, evidence };
  }

  // Writes inline feedback at the bottom of a recommendation card.
  function setCardStatus(card, message, isError = false) {
    const statusElement = card.querySelector(".decision-status");
    if (!statusElement) {
      return;
    }

    statusElement.textContent = message;
    statusElement.classList.toggle("error-message", isError);
  }

  // Locks decision buttons after a decision is saved.
  function disableDecisionButtons(card) {
    card
      .querySelectorAll("[data-decision-action]")
      .forEach((button) => {
        button.disabled = true;
      });
  }

  // Shows an accessible in-page confirmation before saving a decision.
  function confirmDecision(action) {
    return new Promise((resolve) => {
      const isApproval = action === "approved";
      const actionLabel = isApproval ? "approve" : "reject";
      const overlay = document.createElement("div");
      overlay.className = "app-dialog-overlay";
      overlay.innerHTML = `
        <section
          class="app-dialog ${isApproval ? "app-dialog-approve" : "app-dialog-reject"}"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="decisionDialogTitle"
          aria-describedby="decisionDialogMessage"
        >
          <span class="app-dialog-icon" aria-hidden="true">${isApproval ? "✓" : "!"}</span>
          <h2 id="decisionDialogTitle">${isApproval ? "Approve" : "Reject"} recommendation?</h2>
          <p id="decisionDialogMessage">Do you want to ${actionLabel} this recommendation?</p>
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
      confirmButton.focus();
    });
  }

  // Updates the card UI after an approval or rejection is stored.
  function markSavedDecision(card, decision) {
    card.dataset.savedDecision = decision.action;
    card.classList.toggle("is-approved", decision.action === "approved");
    card.classList.toggle("is-rejected", decision.action === "rejected");

    const visibleStatus = card.querySelector(".recommendation-status");
    if (visibleStatus) {
      visibleStatus.textContent =
        decision.action === "approved" ? "Approved" : "Rejected";
      visibleStatus.className =
        `recommendation-status ${
          decision.action === "approved"
            ? "status-approved"
            : "status-rejected"
        }`;
    }

    setCardStatus(
      card,
      `${decision.action === "approved" ? "Approved" : "Rejected"} by ${
        decision.operatorLabel
      } on ${new Date(decision.createdAt).toLocaleString()}`
    );
    disableDecisionButtons(card);
  }

  // Handles one approve/reject button click from the recommendation card.
  async function submitDecision(button) {
    const card = button.closest("[data-recommendation-id]");

    if (!card || card.dataset.savedDecision) {
      return;
    }

    if (!window.APP_USER?.isOperator) {
      setCardStatus(
        card,
        "Only users with the Operator role can approve or reject recommendations.",
        true
      );
      return;
    }

    const recommendationId = card.dataset.recommendationId;
    const recommendationVersion = Number(
      card.dataset.recommendationVersion || "1"
    );
    const action = button.dataset.decisionAction;

    if (action !== "approved" && action !== "rejected") {
      return;
    }

    if (!(await confirmDecision(action))) {
      return;
    }

    const comment = window.prompt(
      "Add an optional decision comment:",
      ""
    );

    if (comment === null) {
      return;
    }

    const cardButtons = [
      ...card.querySelectorAll("[data-decision-action]"),
    ];
    cardButtons.forEach((item) => {
      item.disabled = true;
    });

    setCardStatus(card, "Saving decision…");

    try {
      const response = await apiRequest("/decisions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": createIdempotencyKey(),
        },
        body: JSON.stringify({
          recommendationId,
          recommendationVersion,
          action,
          comment: comment.trim() || null,
          recommendationSnapshot: getCardSnapshot(card),
        }),
      });

      const body = await response.json();
      markSavedDecision(card, body);
    } catch (error) {
      cardButtons.forEach((item) => {
        item.disabled = false;
      });
      setCardStatus(
        card,
        error.message || "The decision could not be saved.",
        true
      );
    }
  }

  // Restores previously saved decisions after recommendation cards render.
  async function restoreSavedDecisions() {
    try {
      const response = await apiRequest("/decisions?limit=500", {
        headers: { Accept: "application/json" },
      });
      const decisions = await response.json();
      const latestByRecommendation = new Map();

      decisions.forEach((decision) => {
        const key =
          `${decision.recommendationId}:` +
          `${decision.recommendationVersion}`;

        if (!latestByRecommendation.has(key)) {
          latestByRecommendation.set(key, decision);
        }
      });

      document
        .querySelectorAll("[data-recommendation-id]")
        .forEach((card) => {
          const recommendationId = card.dataset.recommendationId;
          const recommendationVersion =
            card.dataset.recommendationVersion || "1";
          const decision = latestByRecommendation.get(
            `${recommendationId}:${recommendationVersion}`
          );

          if (decision) {
            markSavedDecision(card, decision);
          }
        });
    } catch (error) {
      console.error("Could not restore saved decisions:", error);
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-decision-action]");
    if (button) {
      submitDecision(button);
    }
  });

  document.addEventListener(
    "recommendations:rendered",
    restoreSavedDecisions
  );
})();

// Saves Operator decisions and supports returning them to pending without deletion.
import { apiRequest } from "./api.js";

(() => {
  "use strict";

  function createIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }

    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }

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
    const priority = card.querySelector(".priority")?.textContent.trim() || "";
    const evidence = [...card.querySelectorAll(
      ".recommendation-evidence-item"
    )].map((item) => item.textContent.replace(/\s+/g, " ").trim());

    return { title, description, reason, priority, evidence };
  }

  function setCardStatus(card, message, isError = false) {
    const statusElement = card.querySelector(".decision-status");
    if (!statusElement) return;

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

  function setVisibleStatus(card, status) {
    const visibleStatus = card.querySelector(".recommendation-status");
    if (!visibleStatus) return;

    const labels = {
      approved: "Approved",
      rejected: "Rejected",
      pending: "Pending review",
    };

    visibleStatus.textContent = labels[status] || labels.pending;
    visibleStatus.className = `recommendation-status status-${status}`;
  }

  function markSavedDecision(card, decision) {
    card.dataset.savedDecision = decision.action;
    card.dataset.activeDecisionId = String(decision.decisionId);
    card.classList.toggle("is-approved", decision.action === "approved");
    card.classList.toggle("is-rejected", decision.action === "rejected");

    setVisibleStatus(card, decision.action);
    setCardStatus(
      card,
      `${decision.action === "approved" ? "Approved" : "Rejected"} by ${
        decision.operatorLabel
      } on ${new Date(decision.createdAt).toLocaleString()}`
    );

    setDecisionButtonsDisabled(card, true);
    const pendingButton = resetButton(card);
    if (pendingButton) {
      pendingButton.hidden = false;
      pendingButton.disabled = false;
    }
  }

  function markPending(card, decision) {
    delete card.dataset.savedDecision;
    delete card.dataset.activeDecisionId;
    card.classList.remove("is-approved", "is-rejected");

    setVisibleStatus(card, "pending");
    setDecisionButtonsDisabled(card, false);

    const pendingButton = resetButton(card);
    if (pendingButton) {
      pendingButton.hidden = true;
      pendingButton.disabled = false;
    }

    const revertedBy = decision.revertedBy || "an Operator";
    const revertedAt = decision.revertedAt
      ? new Date(decision.revertedAt).toLocaleString()
      : new Date().toLocaleString();
    setCardStatus(
      card,
      `Returned to pending by ${revertedBy} on ${revertedAt}`
    );
  }

  function requestWorkflowComment(mode) {
    const settings = {
      approved: {
        dialogClass: "app-dialog-approve",
        icon: "✓",
        title: "Approve this recommendation?",
        message: "Add an optional comment, then confirm your decision.",
        label: "Approve",
        placeholder: "Explain why this recommendation is being approved.",
      },
      rejected: {
        dialogClass: "app-dialog-reject",
        icon: "×",
        title: "Reject this recommendation?",
        message: "Add an optional comment, then confirm your decision.",
        label: "Reject",
        placeholder: "Explain why this recommendation is being rejected.",
      },
      pending: {
        dialogClass: "app-dialog-pending",
        icon: "↺",
        title: "Return this recommendation to pending?",
        message:
          "The previous decision will remain in the audit history but will no longer be active.",
        label: "Set to pending",
        placeholder: "Optionally explain why this decision is being reopened.",
      },
    }[mode];

    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "app-dialog-overlay";
      overlay.setAttribute("role", "presentation");

      const dialog = document.createElement("section");
      dialog.className = `app-dialog ${settings.dialogClass}`;
      dialog.setAttribute("role", "dialog");
      dialog.setAttribute("aria-modal", "true");
      dialog.setAttribute("aria-labelledby", "decisionDialogTitle");

      dialog.innerHTML = `
        <div class="app-dialog-icon" aria-hidden="true">${settings.icon}</div>
        <h2 id="decisionDialogTitle">${settings.title}</h2>
        <p>${settings.message}</p>
        <label
          for="decisionComment"
          style="display:block; margin-top:1rem; text-align:left; font-weight:700;"
        >
          Comment <span style="font-weight:400;">(optional)</span>
        </label>
        <textarea
          id="decisionComment"
          maxlength="1000"
          rows="4"
          placeholder="${settings.placeholder}"
          style="width:100%; margin-top:0.45rem; padding:0.75rem; resize:vertical; border:1px solid #94a3b8; border-radius:6px; font:inherit; color:inherit; background:var(--white);"
        ></textarea>
        <div class="app-dialog-actions">
          <button type="button" class="btn app-dialog-cancel" data-dialog-cancel>
            Cancel
          </button>
          <button type="button" class="btn app-dialog-confirm" data-dialog-confirm>
            ${settings.label}
          </button>
        </div>
      `;

      overlay.appendChild(dialog);
      document.body.appendChild(overlay);

      const commentField = dialog.querySelector("#decisionComment");
      const confirmButton = dialog.querySelector("[data-dialog-confirm]");
      const cancelButton = dialog.querySelector("[data-dialog-cancel]");
      const previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      let finished = false;

      const close = (value) => {
        if (finished) return;
        finished = true;
        document.removeEventListener("keydown", handleKeydown);
        document.body.style.overflow = previousOverflow;
        overlay.remove();
        resolve(value);
      };

      const handleKeydown = (event) => {
        if (event.key === "Escape") close(null);
      };

      confirmButton.addEventListener("click", () => {
        close(commentField.value.trim());
      });
      cancelButton.addEventListener("click", () => close(null));
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay) close(null);
      });
      document.addEventListener("keydown", handleKeydown);
      window.setTimeout(() => commentField.focus(), 0);
    });
  }

  async function submitDecision(button) {
    const card = button.closest("[data-recommendation-id]");
    if (!card || card.dataset.savedDecision) return;

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

    setDecisionButtonsDisabled(card, true);
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
          comment: comment || null,
          recommendationSnapshot: getCardSnapshot(card),
        }),
      });

      markSavedDecision(card, await response.json());
    } catch (error) {
      setDecisionButtonsDisabled(card, false);
      setCardStatus(
        card,
        error.message || "The decision could not be saved.",
        true
      );
    }
  }

  async function submitReset(button) {
    const card = button.closest("[data-recommendation-id]");
    const decisionId = Number(card?.dataset.activeDecisionId || "0");
    if (!card || !decisionId) return;

    if (!window.APP_USER?.isOperator) {
      setCardStatus(
        card,
        "Only users with the Operator role can return a decision to pending.",
        true
      );
      return;
    }

    const comment = await requestWorkflowComment("pending");
    if (comment === null) return;

    button.disabled = true;
    setCardStatus(card, "Returning recommendation to pending…");

    try {
      const response = await apiRequest(
        `/decisions/${decisionId}/reset`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ comment: comment || null }),
        }
      );

      markPending(card, await response.json());
    } catch (error) {
      button.disabled = false;
      setCardStatus(
        card,
        error.message || "The recommendation could not be returned to pending.",
        true
      );
    }
  }

  async function restoreSavedDecisions() {
    try {
      const response = await apiRequest("/decisions?limit=500", {
        headers: { Accept: "application/json" },
      });
      const decisions = await response.json();
      const latestByRecommendation = new Map();

      decisions.forEach((decision) => {
        if (!decision.isActive) return;
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
          const key =
            `${card.dataset.recommendationId}:` +
            `${card.dataset.recommendationVersion || "1"}`;
          const decision = latestByRecommendation.get(key);
          if (decision) markSavedDecision(card, decision);
        });
    } catch (error) {
      console.error("Could not restore saved decisions:", error);
    }
  }

  document.addEventListener("click", (event) => {
    const decisionButton = event.target.closest("[data-decision-action]");
    if (decisionButton) {
      submitDecision(decisionButton);
      return;
    }

    const pendingButton = event.target.closest("[data-reset-decision]");
    if (pendingButton) submitReset(pendingButton);
  });

  document.addEventListener(
    "recommendations:rendered",
    restoreSavedDecisions
  );
})();

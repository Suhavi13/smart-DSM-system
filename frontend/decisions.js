(() => {
  "use strict";

  const API_BASE_URL =
    window.APP_CONFIG?.API_BASE_URL ||
    "http://127.0.0.1:8000/api/v1";

  const KEY_STORAGE_NAME = "gbtacDecisionKey";

  function getDecisionKey() {
    let decisionKey =
      sessionStorage.getItem(KEY_STORAGE_NAME);

    if (decisionKey) {
      return decisionKey;
    }

    decisionKey = window.prompt(
      "Enter the temporary operator decision key:"
    );

    if (!decisionKey) {
      return null;
    }

    decisionKey = decisionKey.trim();

    if (!decisionKey) {
      return null;
    }

    // sessionStorage survives a refresh but is cleared when
    // the browser tab is closed.
    sessionStorage.setItem(
      KEY_STORAGE_NAME,
      decisionKey
    );

    return decisionKey;
  }

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

  function getCardSnapshot(card) {
    const title =
      card.querySelector(
        ".recommendation-title, h2, h3"
      )?.textContent.trim() || "Untitled recommendation";

    const description =
      card.querySelector(
        ".recommendation-description"
      )?.textContent.trim() || "";

    return {
      title,
      description,
    };
  }

  function setCardStatus(
    card,
    message,
    isError = false
  ) {
    const statusElement =
      card.querySelector(".decision-status");

    if (!statusElement) {
      return;
    }

    statusElement.textContent = message;
    statusElement.classList.toggle(
      "error-message",
      isError
    );
  }

  function disableDecisionButtons(card) {
    card
      .querySelectorAll("[data-decision-action]")
      .forEach((button) => {
        button.disabled = true;
      });
  }

  function markSavedDecision(card, decision) {
    card.dataset.savedDecision = decision.action;

    setCardStatus(
      card,
      `${decision.action === "approved"
        ? "Approved"
        : "Disapproved"} on ${new Date(
        decision.createdAt
      ).toLocaleString()}`
    );

    disableDecisionButtons(card);
  }

  async function submitDecision(button) {
    const card = button.closest(
      "[data-recommendation-id]"
    );

    if (!card) {
      return;
    }

    const recommendationId =
      card.dataset.recommendationId;

    const recommendationVersion = Number(
      card.dataset.recommendationVersion || "1"
    );

    const action =
      button.dataset.decisionAction;

    if (
      action !== "approved" &&
      action !== "rejected"
    ) {
      return;
    }

    const confirmationText =
      action === "approved"
        ? "Approve this recommendation?"
        : "Disapprove this recommendation?";

    if (!window.confirm(confirmationText)) {
      return;
    }

    const comment = window.prompt(
      "Add an optional decision comment:",
      ""
    );

    if (comment === null) {
      return;
    }

    const decisionKey = getDecisionKey();

    if (!decisionKey) {
      setCardStatus(
        card,
        "The decision was cancelled because no key was provided.",
        true
      );
      return;
    }

    const cardButtons = [
      ...card.querySelectorAll(
        "[data-decision-action]"
      ),
    ];

    cardButtons.forEach((item) => {
      item.disabled = true;
    });

    setCardStatus(card, "Saving decision...");

    try {
      const response = await fetch(
        `${API_BASE_URL}/decisions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Decision-Key": decisionKey,
            "Idempotency-Key":
              createIdempotencyKey(),
          },
          body: JSON.stringify({
            recommendationId,
            recommendationVersion,
            action,
            comment: comment.trim() || null,
            recommendationSnapshot:
              getCardSnapshot(card),
          }),
        }
      );

      const body = await response.json().catch(
        () => ({})
      );

      if (!response.ok) {
        if (response.status === 401) {
          sessionStorage.removeItem(
            KEY_STORAGE_NAME
          );
        }

        throw new Error(
          body.detail ||
            `Decision request failed (${response.status}).`
        );
      }

      markSavedDecision(card, body);
    } catch (error) {
      cardButtons.forEach((item) => {
        item.disabled = false;
      });

      setCardStatus(
        card,
        error.message ||
          "The decision could not be saved.",
        true
      );
    }
  }

  async function restoreSavedDecisions() {
    const decisionKey =
      sessionStorage.getItem(KEY_STORAGE_NAME);

    if (!decisionKey) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/decisions?limit=500`,
        {
          headers: {
            "X-Decision-Key": decisionKey,
          },
        }
      );

      if (!response.ok) {
        return;
      }

      const decisions = await response.json();

      const latestByRecommendation = new Map();

      decisions.forEach((decision) => {
        const key =
          `${decision.recommendationId}:` +
          `${decision.recommendationVersion}`;

        if (!latestByRecommendation.has(key)) {
          latestByRecommendation.set(
            key,
            decision
          );
        }
      });

      document
        .querySelectorAll(
          "[data-recommendation-id]"
        )
        .forEach((card) => {
          const recommendationId =
            card.dataset.recommendationId;

          const recommendationVersion =
            card.dataset.recommendationVersion ||
            "1";

          const decision =
            latestByRecommendation.get(
              `${recommendationId}:` +
                `${recommendationVersion}`
            );

          if (decision) {
            markSavedDecision(card, decision);
          }
        });
    } catch (error) {
      console.error(
        "Could not restore saved decisions:",
        error
      );
    }
  }

  document.addEventListener(
    "DOMContentLoaded",
    () => {
      document
        .querySelectorAll(
          "[data-decision-action]"
        )
        .forEach((button) => {
          button.addEventListener(
            "click",
            () => submitDecision(button)
          );
        });

      restoreSavedDecisions();
    }
  );
})();
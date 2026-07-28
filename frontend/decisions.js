(() => {
  "use strict";

  const API_BASE_URL =
    window.APP_CONFIG?.API_BASE_URL ||
    "http://127.0.0.1:8000/api/v1";

  const KEY_STORAGE_NAME = "gbtacDecisionKey";
  const recommendationByKey = new Map();

  const recommendationList = document.querySelector("#recommendationList");
  const recommendationCount = document.querySelector("#recommendationCount");
  const recommendationSummary = document.querySelector("#recommendationSummary");

  function recommendationKey(id, version) {
    return `${id}:${version}`;
  }

  function getDecisionKey() {
    let decisionKey = sessionStorage.getItem(KEY_STORAGE_NAME);

    if (decisionKey) {
      return decisionKey;
    }

    decisionKey = window.prompt("Enter the temporary operator decision key:");

    if (!decisionKey?.trim()) {
      return null;
    }

    decisionKey = decisionKey.trim();
    sessionStorage.setItem(KEY_STORAGE_NAME, decisionKey);
    return decisionKey;
  }

  function createIdempotencyKey() {
    if (window.crypto?.randomUUID) {
      return window.crypto.randomUUID();
    }

    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }

  function formatNumber(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return value ?? "Not available";
    }

    return new Intl.NumberFormat("en-CA", {
      maximumFractionDigits: 2,
    }).format(value);
  }

  function formatTimestamp(value) {
    if (!value) return "No timestamp";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleString("en-CA", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  function appendText(parent, tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = text;
    parent.appendChild(element);
    return element;
  }

  function createEvidenceItem(evidence) {
    const item = document.createElement("li");
    item.className = `evidence-item evidence-${evidence.sourceType}`;

    const heading = document.createElement("div");
    heading.className = "evidence-heading";
    appendText(heading, "strong", "", evidence.label);
    appendText(
      heading,
      "span",
      "evidence-source-type",
      evidence.sourceType
    );
    item.appendChild(heading);

    const valueParts = [formatNumber(evidence.value)];
    if (evidence.unit) valueParts.push(evidence.unit);
    appendText(item, "p", "evidence-value", valueParts.join(" "));

    const metadata = [];
    if (evidence.sensorCode) metadata.push(`Sensor: ${evidence.sensorCode}`);
    if (evidence.displayName) metadata.push(evidence.displayName);
    if (evidence.timestamp) metadata.push(formatTimestamp(evidence.timestamp));
    if (evidence.source) metadata.push(`Source: ${evidence.source}`);

    if (metadata.length) {
      appendText(item, "p", "evidence-metadata", metadata.join(" • "));
    }

    if (evidence.rawValue !== null && evidence.rawValue !== undefined) {
      const rawUnit = evidence.rawUnit ? ` ${evidence.rawUnit}` : "";
      appendText(
        item,
        "p",
        "evidence-raw",
        `Raw source value: ${formatNumber(evidence.rawValue)}${rawUnit}`
      );
    }

    if (evidence.note) {
      appendText(item, "p", "evidence-note", evidence.note);
    }

    return item;
  }

  function createRecommendationCard(recommendation) {
    const card = document.createElement("article");
    card.className = "recommendation-card";
    card.dataset.recommendationId = recommendation.recommendationId;
    card.dataset.recommendationVersion = String(
      recommendation.recommendationVersion
    );

    const key = recommendationKey(
      recommendation.recommendationId,
      recommendation.recommendationVersion
    );
    recommendationByKey.set(key, recommendation);

    const main = document.createElement("div");
    main.className = "recommendation-main";

    const titleArea = document.createElement("div");
    appendText(
      titleArea,
      "span",
      "recommendation-category",
      recommendation.category
    );
    appendText(titleArea, "h3", "recommendation-title", recommendation.title);
    appendText(
      titleArea,
      "p",
      "recommendation-description",
      recommendation.description
    );
    main.appendChild(titleArea);

    appendText(
      main,
      "span",
      `priority priority-${recommendation.priority.toLowerCase()}`,
      recommendation.priority
    );
    card.appendChild(main);

    const reason = document.createElement("p");
    reason.className = "recommendation-reason";
    const reasonLabel = document.createElement("strong");
    reasonLabel.textContent = "Why it triggered: ";
    reason.append(reasonLabel, document.createTextNode(recommendation.reason));
    card.appendChild(reason);

    const actionPanel = document.createElement("div");
    actionPanel.className = "recommendation-action-panel";
    appendText(actionPanel, "strong", "", "Recommended operator action");
    appendText(actionPanel, "p", "", recommendation.recommendedAction);
    card.appendChild(actionPanel);

    const evidenceDetails = document.createElement("details");
    evidenceDetails.className = "recommendation-evidence";
    evidenceDetails.open = true;
    const evidenceSummary = document.createElement("summary");
    evidenceSummary.textContent = `Evidence (${recommendation.evidence.length} items)`;
    evidenceDetails.appendChild(evidenceSummary);

    const evidenceList = document.createElement("ul");
    evidenceList.className = "evidence-list";
    recommendation.evidence.forEach((evidence) => {
      evidenceList.appendChild(createEvidenceItem(evidence));
    });
    evidenceDetails.appendChild(evidenceList);
    card.appendChild(evidenceDetails);

    if (recommendation.limitations?.length) {
      const limitations = document.createElement("div");
      limitations.className = "recommendation-limitations";
      appendText(limitations, "strong", "", "Operator checks");
      const list = document.createElement("ul");
      recommendation.limitations.forEach((limitation) => {
        appendText(list, "li", "", limitation);
      });
      limitations.appendChild(list);
      card.appendChild(limitations);
    }

    const meta = document.createElement("div");
    meta.className = "recommendation-meta";
    const statusWrap = document.createElement("span");
    statusWrap.append("Status: ");
    appendText(
      statusWrap,
      "strong",
      "recommendation-status status-pending",
      "Pending review"
    );
    meta.appendChild(statusWrap);
    appendText(meta, "span", "rule-id", `Rule: ${recommendation.ruleId}`);
    card.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "recommendation-actions";

    const approveButton = appendText(
      actions,
      "button",
      "btn recommendation-approve recommendation-action",
      "Approve"
    );
    approveButton.type = "button";
    approveButton.dataset.decisionAction = "approved";

    const rejectButton = appendText(
      actions,
      "button",
      "btn recommendation-reject recommendation-action",
      "Disapprove"
    );
    rejectButton.type = "button";
    rejectButton.dataset.decisionAction = "rejected";

    card.appendChild(actions);
    appendText(card, "p", "decision-status", "").setAttribute(
      "aria-live",
      "polite"
    );

    return card;
  }

  function setCardStatus(card, message, isError = false) {
    const statusElement = card.querySelector(".decision-status");
    if (!statusElement) return;

    statusElement.textContent = message;
    statusElement.classList.toggle("error-message", isError);
  }

  function disableDecisionButtons(card) {
    card.querySelectorAll("[data-decision-action]").forEach((button) => {
      button.disabled = true;
    });
  }

  function markSavedDecision(card, decision) {
    card.dataset.savedDecision = decision.action;
    card.classList.toggle("is-approved", decision.action === "approved");
    card.classList.toggle("is-rejected", decision.action === "rejected");

    const visualStatus = card.querySelector(".recommendation-status");
    if (visualStatus) {
      visualStatus.textContent =
        decision.action === "approved" ? "Approved" : "Disapproved";
      visualStatus.className = `recommendation-status ${
        decision.action === "approved" ? "status-approved" : "status-rejected"
      }`;
    }

    setCardStatus(
      card,
      `${decision.action === "approved" ? "Approved" : "Disapproved"} on ${
        new Date(decision.createdAt).toLocaleString()
      }`
    );
    disableDecisionButtons(card);
  }

  function getCardSnapshot(card) {
    const key = recommendationKey(
      card.dataset.recommendationId,
      card.dataset.recommendationVersion
    );

    return (
      recommendationByKey.get(key) || {
        title:
          card.querySelector(".recommendation-title")?.textContent.trim() ||
          "Untitled recommendation",
        description:
          card
            .querySelector(".recommendation-description")
            ?.textContent.trim() || "",
      }
    );
  }

  async function submitDecision(button) {
    const card = button.closest("[data-recommendation-id]");
    if (!card) return;

    const recommendationId = card.dataset.recommendationId;
    const recommendationVersion = Number(
      card.dataset.recommendationVersion || "1"
    );
    const action = button.dataset.decisionAction;

    if (action !== "approved" && action !== "rejected") return;

    const confirmationText =
      action === "approved"
        ? "Approve this recommendation?"
        : "Disapprove this recommendation?";

    if (!window.confirm(confirmationText)) return;

    const comment = window.prompt("Add an optional decision comment:", "");
    if (comment === null) return;

    const decisionKey = getDecisionKey();
    if (!decisionKey) {
      setCardStatus(
        card,
        "The decision was cancelled because no key was provided.",
        true
      );
      return;
    }

    const cardButtons = [...card.querySelectorAll("[data-decision-action]")];
    cardButtons.forEach((item) => {
      item.disabled = true;
    });
    setCardStatus(card, "Saving decision...");

    try {
      const response = await fetch(`${API_BASE_URL}/decisions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Decision-Key": decisionKey,
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

      const body = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401) {
          sessionStorage.removeItem(KEY_STORAGE_NAME);
        }
        throw new Error(
          body.detail || `Decision request failed (${response.status}).`
        );
      }

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

  async function restoreSavedDecisions() {
    const decisionKey = sessionStorage.getItem(KEY_STORAGE_NAME);
    if (!decisionKey) return;

    try {
      const response = await fetch(`${API_BASE_URL}/decisions?limit=500`, {
        headers: { "X-Decision-Key": decisionKey },
      });
      if (!response.ok) return;

      const decisions = await response.json();
      const latestByRecommendation = new Map();

      decisions.forEach((decision) => {
        const key = recommendationKey(
          decision.recommendationId,
          decision.recommendationVersion
        );
        if (!latestByRecommendation.has(key)) {
          latestByRecommendation.set(key, decision);
        }
      });

      document
        .querySelectorAll("[data-recommendation-id]")
        .forEach((card) => {
          const decision = latestByRecommendation.get(
            recommendationKey(
              card.dataset.recommendationId,
              card.dataset.recommendationVersion
            )
          );
          if (decision) markSavedDecision(card, decision);
        });
    } catch (error) {
      console.error("Could not restore saved decisions:", error);
    }
  }

  function renderEmptyState(payload) {
    const message = document.createElement("article");
    message.className = "recommendation-empty-state";
    appendText(message, "h2", "", "No rules are currently triggered");
    appendText(
      message,
      "p",
      "",
      "The service evaluated the available sensor and weather evidence without finding a threshold violation."
    );
    recommendationList.appendChild(message);

    recommendationSummary.textContent = `${payload.evaluatedRuleCount} rules evaluated. No recommendation requires review.`;
  }

  async function loadRecommendations() {
    if (!recommendationList) return;

    recommendationList.setAttribute("aria-busy", "true");
    recommendationList.replaceChildren();
    recommendationByKey.clear();

    try {
      const response = await fetch(`${API_BASE_URL}/recommendations`, {
        headers: { Accept: "application/json" },
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          payload.detail || `Recommendation request failed (${response.status}).`
        );
      }

      recommendationCount.textContent = String(payload.recommendationCount);

      if (!payload.recommendations.length) {
        renderEmptyState(payload);
      } else {
        payload.recommendations.forEach((recommendation) => {
          recommendationList.appendChild(
            createRecommendationCard(recommendation)
          );
        });

        const datasetTime = payload.datasetLatestTimestamp
          ? formatTimestamp(payload.datasetLatestTimestamp)
          : "not available";
        recommendationSummary.textContent = `${payload.evaluatedRuleCount} rules evaluated; ${payload.recommendationCount} triggered. Latest sensor evidence: ${datasetTime}. External data: ${payload.externalDataStatus}.`;
      }

      if (payload.warnings?.length) {
        recommendationSummary.textContent += ` ${payload.warnings.join(" ")}`;
      }

      await restoreSavedDecisions();
    } catch (error) {
      recommendationCount.textContent = "--";
      recommendationSummary.textContent = "Recommendations could not be loaded.";
      const errorCard = document.createElement("article");
      errorCard.className = "recommendation-empty-state error-message";
      appendText(errorCard, "h2", "", "Recommendation service unavailable");
      appendText(
        errorCard,
        "p",
        "",
        error.message || "Check that the FastAPI backend is running."
      );
      recommendationList.appendChild(errorCard);
    } finally {
      recommendationList.setAttribute("aria-busy", "false");
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-decision-action]");
    if (button) submitDecision(button);
  });

  document.addEventListener("DOMContentLoaded", loadRecommendations);
})();

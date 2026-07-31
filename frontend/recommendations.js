// Renders recommendation cards from the backend recommendation service.
import { apiGet } from "./api.js";

(() => {
  "use strict";

  // Main page targets where recommendation cards and summary text appear.
  const recommendationList = document.getElementById("recommendationList");
  const recommendationSummary = document.getElementById("recommendationSummary");
  const recommendationNotice = document.getElementById("recommendationDataNotice");

  if (!recommendationList) {
    return;
  }

  // Escapes text before placing it inside generated HTML.
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // Formats evidence numbers with readable units for the card display.
  function formatEvidenceValue(evidence) {
    const numericValue = Number(evidence.value);
    if (!Number.isFinite(numericValue)) {
      return "Unavailable";
    }

    const digits = Math.abs(numericValue) >= 1000 ? 0 : 1;
    return `${numericValue.toLocaleString(undefined, {
      maximumFractionDigits: digits,
    })} ${evidence.unit || ""}`.trim();
  }

  // Converts recommendation timestamps into local date/time text.
  function formatTimestamp(timestamp) {
    if (!timestamp) {
      return "Timestamp unavailable";
    }

    const parsed = new Date(timestamp);
    if (Number.isNaN(parsed.getTime())) {
      return String(timestamp);
    }

    return parsed.toLocaleString();
  }

  // Builds the evidence list shown inside the expandable card section.
  function renderEvidence(evidenceItems) {
    return evidenceItems
      .map(
        (evidence) => `
          <li class="recommendation-evidence-item">
            <div class="recommendation-evidence-heading">
              <strong>${escapeHtml(evidence.label)}</strong>
              <span class="evidence-type evidence-${escapeHtml(
                evidence.evidenceType
              )}">${escapeHtml(evidence.evidenceType)}</span>
            </div>
            <p class="recommendation-evidence-value">
              ${escapeHtml(formatEvidenceValue(evidence))}
            </p>
            <p>${escapeHtml(evidence.comparison)}</p>
            <p>${escapeHtml(evidence.details)}</p>
            <p class="recommendation-evidence-source">
              Source: ${escapeHtml(evidence.sourceName)}
              ${
                evidence.sourceCodes?.length
                  ? ` (${escapeHtml(evidence.sourceCodes.join(", "))})`
                  : ""
              }
              &middot; ${escapeHtml(formatTimestamp(evidence.timestamp))}
            </p>
          </li>
        `
      )
      .join("");
  }

  // Builds one recommendation card with title, priority, reason, evidence, and actions.
  function renderRecommendation(recommendation) {
  return `
    <article
      class="recommendation-card"
      data-recommendation-id="${escapeHtml(
        recommendation.recommendationId
      )}"
      data-recommendation-version="${escapeHtml(
        recommendation.recommendationVersion
      )}"
    >
      <div class="recommendation-main">
        <div>
          <h3 class="recommendation-title">${escapeHtml(
            recommendation.title
          )}</h3>
        </div>

        <span class="priority priority-${escapeHtml(
          recommendation.priority.toLowerCase()
        )}">
          ${escapeHtml(recommendation.priority)}
        </span>
      </div>
      
      <div class="recommendation-description">
       ${escapeHtml(recommendation.description)
         .replace(
           /Recommendation:/g,
            "<strong>Recommendation:</strong>"
           )
            .replace(
               /Reason:/g,
                "<br><br><strong>Reason:</strong>"
               )
                .replace(
                   /Expected Benefit:/g,
                    "<br><br><strong>Expected Benefit:</strong>"
                   )
                    .replace(/&lt;br&gt;/g, "<br>")
                    .replace(/&lt;strong&gt;/g, "<strong>")
                    .replace(/&lt;\/strong&gt;/g, "</strong>")}
      </div>

      <div class="recommendation-meta">
        <span>
          Status:
          <strong class="recommendation-status status-pending">
            Pending review
          </strong>
        </span>
       </div>

        <div class="recommendation-actions" data-operator-only hidden>
          <button
            type="button"
            class="btn recommendation-approve recommendation-action"
            data-decision-action="approved"
          >
            Approve
          </button>
          <button
            type="button"
            class="btn recommendation-reject recommendation-action"
            data-decision-action="rejected"
          >
            Reject
          </button>
        </div>

      <p class="decision-status" role="status" aria-live="polite"></p>
    </article>
  `;
}

  // Shows a friendly empty state when no recommendation rules are triggered.
  function renderNoRecommendations(data) {
    const evaluationItems = (data.evaluations || [])
      .map(
        (evaluation) => `
          <li>
            <strong>${escapeHtml(evaluation.ruleName)}:</strong>
            ${escapeHtml(evaluation.summary)}
          </li>
        `
      )
      .join("");

    recommendationList.innerHTML = `
      <section class="recommendation-empty-state">
        <h2>No active recommendations</h2>
        <p>None of the three configured rules currently exceeds its trigger.</p>
        <ul class="recommendation-evaluation-list">${evaluationItems}</ul>
      </section>
    `;
  }

  // Loads recommendation data and replaces the loading text with visible cards.
  async function loadRecommendations() {
    recommendationList.innerHTML = `
      <p class="recommendation-loading" role="status">
        Evaluating sensor and weather rules&hellip;
      </p>
    `;

    try {
      const data = await apiGet("/recommendations");

      if (recommendationSummary) {
        recommendationSummary.textContent =
         `${data.recommendationCount} recommendation${
           data.recommendationCount === 1 ? "" : "s"
           } available`;
          }

      if (recommendationNotice) {
         recommendationNotice.remove();
        }

      if (!data.recommendations?.length) {
        renderNoRecommendations(data);
      } else {
        recommendationList.innerHTML = data.recommendations
          .map(renderRecommendation)
          .join("");
      }

      document.dispatchEvent(
        new CustomEvent("recommendations:rendered", {
          detail: data,
        })
      );
    } catch (error) {
      recommendationList.innerHTML = `
        <section class="recommendation-error-state" role="alert">
          <h2>Recommendations could not be loaded</h2>
          <p>${escapeHtml(error.message || "The API request failed.")}</p>
        </section>
      `;

      if (recommendationSummary) {
        recommendationSummary.textContent = "Recommendation API unavailable";
      }
    }
  }

  document.addEventListener("authentication:ready", (event) => {
    if (event.detail?.isOperator) {
      loadRecommendations();
    }
  });

  if (window.APP_USER?.isOperator) {
    loadRecommendations();
  }
})();

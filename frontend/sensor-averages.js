// Interactive historical sensor-average explorer for the Sensors page.
import { apiGet, apiRequest } from "./api.js";

const tableBody = document.getElementById("sensorAverageTableBody");
const searchInput = document.getElementById("averageSensorSearch");
const startDateInput = document.getElementById("averageStartDate");
const endDateInput = document.getElementById("averageEndDate");
const selectAllCheckbox = document.getElementById("averageSelectAll");
const selectVisibleButton = document.getElementById(
  "selectVisibleAverageSensors"
);
const clearButton = document.getElementById("clearAverageSensors");
const calculateButton = document.getElementById("calculateSensorAverages");
const selectedCount = document.getElementById("averageSelectedCount");
const statusElement = document.getElementById("sensorAverageStatus");

let sensors = [];
const selectedCodes = new Set();
const averagesByCode = new Map();

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";

  return number.toLocaleString(undefined, {
    maximumFractionDigits: 3,
  });
}

function formatCount(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString() : "—";
}

function normalizedSearchValue(sensor) {
  return [
    sensor.sensorCode,
    sensor.displayName,
    sensor.category,
    sensor.displayUnit,
    sensor.rawUnit,
    sensor.location,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function visibleSensors() {
  const search = String(searchInput?.value || "").trim().toLowerCase();
  if (!search) return sensors;
  return sensors.filter((sensor) =>
    normalizedSearchValue(sensor).includes(search)
  );
}

function setStatus(message, state = "normal") {
  if (!statusElement) return;
  statusElement.textContent = message;
  statusElement.dataset.state = state;
}

function updateSelectionSummary() {
  if (selectedCount) {
    selectedCount.textContent = `${selectedCodes.size} selected`;
  }

  const visible = visibleSensors();
  const selectedVisible = visible.filter((sensor) =>
    selectedCodes.has(sensor.sensorCode)
  ).length;

  if (selectAllCheckbox) {
    selectAllCheckbox.checked =
      visible.length > 0 && selectedVisible === visible.length;
    selectAllCheckbox.indeterminate =
      selectedVisible > 0 && selectedVisible < visible.length;
  }

  if (calculateButton) {
    calculateButton.disabled = selectedCodes.size === 0;
  }
}

function resultCells(sensor) {
  const result = averagesByCode.get(sensor.sensorCode);
  if (!result) {
    return {
      readingCount: "—",
      average: "—",
      minimum: "—",
      maximum: "—",
    };
  }

  if (result.readingCount === 0) {
    return {
      readingCount: "0",
      average: "No readings",
      minimum: "—",
      maximum: "—",
    };
  }

  return {
    readingCount: formatCount(result.readingCount),
    average: formatNumber(result.averageValue),
    minimum: formatNumber(result.minimumValue),
    maximum: formatNumber(result.maximumValue),
  };
}

function renderTable() {
  if (!tableBody) return;

  const visible = visibleSensors();
  tableBody.innerHTML = visible
    .map((sensor) => {
      const isSelected = selectedCodes.has(sensor.sensorCode);
      const result = resultCells(sensor);
      const unit = sensor.displayUnit || sensor.rawUnit || "Unconfirmed";

      return `
        <tr class="${isSelected ? "is-selected" : ""}">
          <td class="sensor-average-select-column">
            <input
              class="sensor-average-checkbox"
              type="checkbox"
              value="${escapeHtml(sensor.sensorCode)}"
              aria-label="Select ${escapeHtml(sensor.displayName)}"
              ${isSelected ? "checked" : ""}
            />
          </td>
          <td><strong>${escapeHtml(sensor.sensorCode)}</strong></td>
          <td>${escapeHtml(sensor.displayName)}</td>
          <td>${escapeHtml(sensor.category || "Uncategorized")}</td>
          <td>${escapeHtml(unit)}</td>
          <td>${escapeHtml(result.readingCount)}</td>
          <td class="sensor-average-result">${escapeHtml(result.average)}</td>
          <td>${escapeHtml(result.minimum)}</td>
          <td>${escapeHtml(result.maximum)}</td>
        </tr>`;
    })
    .join("");

  if (visible.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="9" class="sensor-average-empty">
          No sensors match this search.
        </td>
      </tr>`;
  }

  updateSelectionSummary();
}

function clearCalculatedResults(message) {
  averagesByCode.clear();
  renderTable();
  if (message) setStatus(message);
}

function requestDateRange() {
  const startDate = startDateInput?.value || "";
  const endDate = endDateInput?.value || "";

  if (startDate && endDate && startDate > endDate) {
    throw new Error("The start date must be before the end date.");
  }

  return {
    start: startDate ? `${startDate}T00:00:00` : null,
    end: endDate ? `${endDate}T23:59:59` : null,
  };
}

async function calculateAverages() {
  if (selectedCodes.size === 0) {
    setStatus("Select at least one sensor before calculating.", "error");
    return;
  }

  let range;
  try {
    range = requestDateRange();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }

  calculateButton.disabled = true;
  calculateButton.textContent = "Calculating…";
  setStatus(
    `Calculating averages for ${selectedCodes.size} selected sensor(s)…`,
    "loading"
  );

  try {
    const response = await apiRequest("/sensors/averages", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sensorCodes: Array.from(selectedCodes),
        start: range.start,
        end: range.end,
      }),
    });
    const payload = await response.json();

    averagesByCode.clear();
    payload.sensors.forEach((result) => {
      averagesByCode.set(result.sensorCode, result);
    });
    renderTable();

    const dateDescription =
      range.start || range.end
        ? "within the selected date range"
        : "across all imported readings";
    const missingDescription = payload.missingSensorCodes?.length
      ? ` ${payload.missingSensorCodes.length} sensor(s) were not found.`
      : "";

    setStatus(
      `Calculated ${payload.returnedSensorCount} sensor average(s) ${dateDescription}.${missingDescription}`,
      payload.missingSensorCodes?.length ? "warning" : "success"
    );
  } catch (error) {
    console.error("Could not calculate sensor averages:", error);
    setStatus(error.message || "Could not calculate sensor averages.", "error");
  } finally {
    calculateButton.textContent = "Calculate averages";
    updateSelectionSummary();
  }
}

async function loadSensors() {
  if (!tableBody) return;

  try {
    sensors = await apiGet("/sensors?includeLatest=true");
    sensors.sort((left, right) =>
      String(left.displayName || left.sensorCode).localeCompare(
        String(right.displayName || right.sensorCode)
      )
    );
    renderTable();
    setStatus(
      `Choose from ${sensors.length} available sensors. Averages are calculated separately for each sensor.`
    );
  } catch (error) {
    console.error("Could not load sensors for averages:", error);
    setStatus(error.message || "Could not load the sensor list.", "error");
    tableBody.innerHTML = `
      <tr>
        <td colspan="9" class="sensor-average-empty">
          Could not load sensors from the API.
        </td>
      </tr>`;
  }
}

searchInput?.addEventListener("input", renderTable);

tableBody?.addEventListener("change", (event) => {
  const checkbox = event.target.closest(".sensor-average-checkbox");
  if (!checkbox) return;

  if (checkbox.checked) {
    selectedCodes.add(checkbox.value);
  } else {
    selectedCodes.delete(checkbox.value);
  }
  renderTable();
});

selectAllCheckbox?.addEventListener("change", () => {
  visibleSensors().forEach((sensor) => {
    if (selectAllCheckbox.checked) {
      selectedCodes.add(sensor.sensorCode);
    } else {
      selectedCodes.delete(sensor.sensorCode);
    }
  });
  renderTable();
});

selectVisibleButton?.addEventListener("click", () => {
  visibleSensors().forEach((sensor) => selectedCodes.add(sensor.sensorCode));
  renderTable();
});

clearButton?.addEventListener("click", () => {
  selectedCodes.clear();
  averagesByCode.clear();
  renderTable();
  setStatus("Selection cleared.");
});

calculateButton?.addEventListener("click", calculateAverages);

[startDateInput, endDateInput].forEach((input) => {
  input?.addEventListener("change", () => {
    clearCalculatedResults("Date range changed. Calculate again to refresh the averages.");
  });
});

loadSensors();

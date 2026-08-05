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
const chartPanel = document.getElementById("sensorAverageChartPanel");
const chartCanvas = document.getElementById("sensorAverageChart");
const chartFrame = document.getElementById("sensorAverageChartFrame");
const chartEmpty = document.getElementById("sensorAverageChartEmpty");
const chartSummary = document.getElementById("sensorAverageChartSummary");
const chartUnitSelect = document.getElementById("averageChartUnit");
const chartUnitControl = document.getElementById("averageChartUnitControl");

let sensors = [];
const selectedCodes = new Set();
const averagesByCode = new Map();
let averageChart = null;

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

function renderTable() {
  if (!tableBody) return;

  const visible = visibleSensors();
  tableBody.innerHTML = visible
    .map((sensor) => {
      const isSelected = selectedCodes.has(sensor.sensorCode);
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
        </tr>`;
    })
    .join("");

  if (visible.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" class="sensor-average-empty">
          No sensors match this search.
        </td>
      </tr>`;
  }

  updateSelectionSummary();
}

function destroyAverageChart() {
  if (averageChart) {
    averageChart.destroy();
    averageChart = null;
  }
}

function hideAverageChart() {
  destroyAverageChart();
  if (chartPanel) chartPanel.hidden = true;
  if (chartEmpty) chartEmpty.hidden = true;
  if (chartCanvas) chartCanvas.hidden = false;
  if (chartSummary) chartSummary.textContent = "";
}

function clearCalculatedResults(message) {
  averagesByCode.clear();
  hideAverageChart();
  if (message) setStatus(message);
}

function invalidateResultsAfterSelectionChange() {
  if (averagesByCode.size === 0) return;
  clearCalculatedResults(
    "Sensor selection changed. Calculate again to update the graph."
  );
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

function resultUnit(result) {
  return String(result.displayUnit || "Unconfirmed").trim() || "Unconfirmed";
}

function graphableResults() {
  return Array.from(averagesByCode.values()).filter(
    (result) =>
      selectedCodes.has(result.sensorCode) &&
      Number(result.readingCount) > 0 &&
      Number.isFinite(Number(result.averageValue))
  );
}

function resultsGroupedByUnit() {
  const grouped = new Map();

  graphableResults().forEach((result) => {
    const unit = resultUnit(result);
    if (!grouped.has(unit)) grouped.set(unit, []);
    grouped.get(unit).push(result);
  });

  return grouped;
}

function updateUnitOptions(groupedResults) {
  if (!chartUnitSelect) return null;

  const previousUnit = chartUnitSelect.value;
  const units = Array.from(groupedResults.entries())
    .sort((left, right) => {
      const countDifference = right[1].length - left[1].length;
      return countDifference || left[0].localeCompare(right[0]);
    })
    .map(([unit]) => unit);

  chartUnitSelect.innerHTML = units
    .map(
      (unit) =>
        `<option value="${escapeHtml(unit)}">${escapeHtml(unit)}</option>`
    )
    .join("");

  if (units.includes(previousUnit)) {
    chartUnitSelect.value = previousUnit;
  }

  if (chartUnitControl) {
    chartUnitControl.hidden = units.length <= 1;
  }

  return chartUnitSelect.value || units[0] || null;
}

function cssColor(variableName, fallback) {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(variableName)
    .trim();
  return value || fallback;
}

function chartTheme() {
  const isDark = document.documentElement.dataset.theme === "dark";
  return {
    text: cssColor("--text", isDark ? "#e5edf8" : "#222222"),
    muted: cssColor("--muted", isDark ? "#b8c5d6" : "#64748b"),
    bar: cssColor("--secondary", "#5a0d73"),
    border: cssColor("--primary", "#1e9bd1"),
    grid: isDark ? "rgba(184, 197, 214, 0.2)" : "rgba(100, 116, 139, 0.18)",
  };
}

function showChartEmpty(message) {
  destroyAverageChart();
  if (chartPanel) chartPanel.hidden = false;
  if (chartCanvas) chartCanvas.hidden = true;
  if (chartEmpty) {
    chartEmpty.hidden = false;
    chartEmpty.textContent = message;
  }
  if (chartSummary) chartSummary.textContent = message;
}

function renderAverageChart() {
  if (!chartCanvas || !chartPanel) return;

  const ChartConstructor = window.Chart;
  if (typeof ChartConstructor !== "function") {
    showChartEmpty(
      "The graph library did not load. Check the internet connection and refresh the page."
    );
    return;
  }

  const groupedResults = resultsGroupedByUnit();
  const selectedUnit = updateUnitOptions(groupedResults);

  if (!selectedUnit) {
    showChartEmpty("No numeric readings were available for the selected sensors.");
    return;
  }

  const rows = [...(groupedResults.get(selectedUnit) || [])].sort((left, right) =>
    String(left.displayName || left.sensorCode).localeCompare(
      String(right.displayName || right.sensorCode)
    )
  );

  if (rows.length === 0) {
    showChartEmpty(`No numeric readings were available in ${selectedUnit}.`);
    return;
  }

  destroyAverageChart();
  chartPanel.hidden = false;
  chartCanvas.hidden = false;
  if (chartEmpty) chartEmpty.hidden = true;

  const chartHeight = Math.max(300, Math.min(rows.length * 44 + 90, 5200));
  if (chartFrame) chartFrame.style.height = `${chartHeight}px`;

  const groupedSensorCount = Array.from(groupedResults.values()).reduce(
    (total, group) => total + group.length,
    0
  );
  const excludedCount = selectedCodes.size - groupedSensorCount;
  const unitGroupText =
    groupedResults.size > 1
      ? ` Showing ${rows.length} sensor(s) measured in ${selectedUnit}; choose another unit to view the other groups.`
      : ` Showing ${rows.length} sensor(s) measured in ${selectedUnit}.`;
  const excludedText =
    excludedCount > 0
      ? ` ${excludedCount} selected sensor(s) had no numeric readings in the chosen date range.`
      : "";

  if (chartSummary) {
    chartSummary.textContent = `${unitGroupText.trim()}${excludedText}`;
  }

  const theme = chartTheme();
  const context = chartCanvas.getContext("2d");

  averageChart = new ChartConstructor(context, {
    type: "bar",
    data: {
      labels: rows.map(
        (result) => `${result.sensorCode} — ${result.displayName}`
      ),
      datasets: [
        {
          label: `Average (${selectedUnit})`,
          data: rows.map((result) => Number(result.averageValue)),
          backgroundColor: theme.bar,
          borderColor: theme.border,
          borderWidth: 1,
          borderRadius: 5,
          borderSkipped: false,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: rows.length <= 30,
      interaction: {
        mode: "nearest",
        intersect: true,
      },
      scales: {
        x: {
          beginAtZero: false,
          title: {
            display: true,
            text: `Average reading (${selectedUnit})`,
            color: theme.text,
            font: { weight: "bold" },
          },
          ticks: {
            color: theme.muted,
            callback: (value) => formatNumber(value),
          },
          grid: { color: theme.grid },
        },
        y: {
          ticks: {
            color: theme.text,
            autoSkip: false,
            font: { size: 11 },
          },
          grid: { display: false },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => {
              const result = rows[items[0]?.dataIndex];
              return result
                ? [`${result.displayName}`, result.sensorCode]
                : [];
            },
            label: (item) =>
              `Average: ${formatNumber(item.raw)} ${selectedUnit}`,
            afterLabel: (item) => {
              const result = rows[item.dataIndex];
              return [
                `Minimum: ${formatNumber(result.minimumValue)} ${selectedUnit}`,
                `Maximum: ${formatNumber(result.maximumValue)} ${selectedUnit}`,
                `Readings: ${formatCount(result.readingCount)}`,
              ];
            },
          },
        },
      },
    },
  });
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
    renderAverageChart();

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
    hideAverageChart();
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
      `Choose from ${sensors.length} available sensors. Averages are displayed as a graph after calculation.`
    );
  } catch (error) {
    console.error("Could not load sensors for averages:", error);
    setStatus(error.message || "Could not load the sensor list.", "error");
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" class="sensor-average-empty">
          Could not load sensors from the API.
        </td>
      </tr>`;
  }
}

searchInput?.addEventListener("input", renderTable);

tableBody?.addEventListener("change", (event) => {
  const checkbox = event.target.closest(".sensor-average-checkbox");
  if (!checkbox) return;

  invalidateResultsAfterSelectionChange();
  if (checkbox.checked) {
    selectedCodes.add(checkbox.value);
  } else {
    selectedCodes.delete(checkbox.value);
  }
  renderTable();
});

selectAllCheckbox?.addEventListener("change", () => {
  invalidateResultsAfterSelectionChange();
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
  invalidateResultsAfterSelectionChange();
  visibleSensors().forEach((sensor) => selectedCodes.add(sensor.sensorCode));
  renderTable();
});

clearButton?.addEventListener("click", () => {
  selectedCodes.clear();
  averagesByCode.clear();
  hideAverageChart();
  renderTable();
  setStatus("Selection cleared.");
});

calculateButton?.addEventListener("click", calculateAverages);
chartUnitSelect?.addEventListener("change", renderAverageChart);

[startDateInput, endDateInput].forEach((input) => {
  input?.addEventListener("change", () => {
    clearCalculatedResults(
      "Date range changed. Calculate again to update the graph."
    );
  });
});

// Re-render the canvas when the shared light/dark theme changes.
new MutationObserver(() => {
  if (averagesByCode.size > 0) renderAverageChart();
}).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-theme"],
});

loadSensors();

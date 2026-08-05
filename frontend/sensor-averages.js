// Compact historical sensor-average explorer for the Sensors page.
import { apiGet, apiRequest } from "./api.js";

const PICKER_PAGE_SIZE = 12;
const CHART_PAGE_SIZE = 12;
const SELECTED_PREVIEW_LIMIT = 8;

const tableBody = document.getElementById("sensorAverageTableBody");
const searchInput = document.getElementById("averageSensorSearch");
const categoryFilter = document.getElementById("averageSensorCategory");
const unitFilter = document.getElementById("averageSensorUnit");
const selectedOnlyFilter = document.getElementById("averageSelectedOnly");
const startDateInput = document.getElementById("averageStartDate");
const endDateInput = document.getElementById("averageEndDate");
const selectPageButton = document.getElementById("selectAverageSensorPage");
const clearFiltersButton = document.getElementById("clearAverageSensorFilters");
const clearButton = document.getElementById("clearAverageSensors");
const calculateButton = document.getElementById("calculateSensorAverages");
const selectedCount = document.getElementById("averageSelectedCount");
const selectedHelp = document.getElementById("averageSelectedHelp");
const selectedPreview = document.getElementById("averageSelectedPreview");
const statusElement = document.getElementById("sensorAverageStatus");

const pickerPanel = document.getElementById("averageSensorPicker");
const pickerToggle = document.getElementById("toggleAverageSensorPicker");
const pickerClose = document.getElementById("closeAverageSensorPicker");
const pickerResultCount = document.getElementById("sensorPickerResultCount");
const pickerPrevious = document.getElementById("averagePickerPrevious");
const pickerNext = document.getElementById("averagePickerNext");
const pickerPageText = document.getElementById("averagePickerPage");

const chartPanel = document.getElementById("sensorAverageChartPanel");
const chartCanvas = document.getElementById("sensorAverageChart");
const chartFrame = document.getElementById("sensorAverageChartFrame");
const chartEmpty = document.getElementById("sensorAverageChartEmpty");
const chartSummary = document.getElementById("sensorAverageChartSummary");
const chartUnitSelect = document.getElementById("averageChartUnit");
const chartUnitControl = document.getElementById("averageChartUnitControl");
const chartSortSelect = document.getElementById("averageChartSort");
const chartPagination = document.getElementById("averageChartPagination");
const chartPrevious = document.getElementById("averageChartPrevious");
const chartNext = document.getElementById("averageChartNext");
const chartPageText = document.getElementById("averageChartPage");

let sensors = [];
const selectedCodes = new Set();
const averagesByCode = new Map();
let averageChart = null;
let pickerPage = 1;
let chartPage = 1;

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
  return number.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function formatCount(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString() : "—";
}

function sensorUnit(sensor) {
  return String(sensor.displayUnit || sensor.rawUnit || "Unconfirmed").trim();
}

function sensorName(sensor) {
  return String(sensor.displayName || sensor.sensorCode || "Unknown sensor");
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

function filteredSensors() {
  const search = String(searchInput?.value || "").trim().toLowerCase();
  const category = categoryFilter?.value || "";
  const unit = unitFilter?.value || "";
  const selectedOnly = Boolean(selectedOnlyFilter?.checked);

  return sensors.filter((sensor) => {
    if (search && !normalizedSearchValue(sensor).includes(search)) return false;
    if (category && String(sensor.category || "Uncategorized") !== category) return false;
    if (unit && sensorUnit(sensor) !== unit) return false;
    if (selectedOnly && !selectedCodes.has(sensor.sensorCode)) return false;
    return true;
  });
}

function pickerPageData() {
  const filtered = filteredSensors();
  const pageCount = Math.max(1, Math.ceil(filtered.length / PICKER_PAGE_SIZE));
  pickerPage = Math.min(Math.max(1, pickerPage), pageCount);
  const start = (pickerPage - 1) * PICKER_PAGE_SIZE;
  return {
    filtered,
    pageCount,
    rows: filtered.slice(start, start + PICKER_PAGE_SIZE),
    start,
  };
}

function setStatus(message, state = "normal") {
  if (!statusElement) return;
  statusElement.textContent = message;
  statusElement.dataset.state = state;
}

function populateFilterOptions() {
  const categories = [...new Set(
    sensors.map((sensor) => String(sensor.category || "Uncategorized"))
  )].sort((a, b) => a.localeCompare(b));
  const units = [...new Set(sensors.map(sensorUnit))].sort((a, b) =>
    a.localeCompare(b)
  );

  if (categoryFilter) {
    categoryFilter.innerHTML = [
      '<option value="">All types</option>',
      ...categories.map(
        (category) =>
          `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`
      ),
    ].join("");
  }

  if (unitFilter) {
    unitFilter.innerHTML = [
      '<option value="">All units</option>',
      ...units.map(
        (unit) => `<option value="${escapeHtml(unit)}">${escapeHtml(unit)}</option>`
      ),
    ].join("");
  }
}

function renderSelectedPreview() {
  if (!selectedPreview || !selectedHelp) return;

  const selectedSensors = sensors
    .filter((sensor) => selectedCodes.has(sensor.sensorCode))
    .sort((left, right) => sensorName(left).localeCompare(sensorName(right)));

  if (selectedSensors.length === 0) {
    selectedHelp.textContent = "No sensors selected yet.";
    selectedPreview.innerHTML = "";
    return;
  }

  selectedHelp.textContent =
    selectedSensors.length === 1
      ? "1 sensor will be included in the calculation."
      : `${selectedSensors.length} sensors will be included. The graph shows 12 bars per page.`;

  const previewRows = selectedSensors.slice(0, SELECTED_PREVIEW_LIMIT);
  selectedPreview.innerHTML = previewRows
    .map(
      (sensor) => `
        <span class="sensor-selected-chip">
          <span title="${escapeHtml(sensorName(sensor))}">${escapeHtml(sensorName(sensor))}</span>
          <button
            type="button"
            data-remove-average-sensor="${escapeHtml(sensor.sensorCode)}"
            aria-label="Remove ${escapeHtml(sensorName(sensor))}"
          >×</button>
        </span>`
    )
    .join("");

  if (selectedSensors.length > SELECTED_PREVIEW_LIMIT) {
    selectedPreview.insertAdjacentHTML(
      "beforeend",
      `<span class="sensor-selected-more">+${selectedSensors.length - SELECTED_PREVIEW_LIMIT} more</span>`
    );
  }
}

function updateSelectionSummary() {
  if (selectedCount) selectedCount.textContent = `${selectedCodes.size} selected`;
  if (calculateButton) calculateButton.disabled = selectedCodes.size === 0;
  if (clearButton) clearButton.disabled = selectedCodes.size === 0;
  renderSelectedPreview();
}

function renderPicker() {
  if (!tableBody) return;

  const { filtered, pageCount, rows, start } = pickerPageData();
  tableBody.innerHTML = rows
    .map((sensor) => {
      const isSelected = selectedCodes.has(sensor.sensorCode);
      return `
        <tr class="${isSelected ? "is-selected" : ""}">
          <td class="sensor-average-select-column">
            <input
              class="sensor-average-checkbox"
              type="checkbox"
              value="${escapeHtml(sensor.sensorCode)}"
              aria-label="Select ${escapeHtml(sensorName(sensor))}"
              ${isSelected ? "checked" : ""}
            />
          </td>
          <td>
            <span class="sensor-picker-name">
              <strong>${escapeHtml(sensorName(sensor))}</strong>
              <small>${escapeHtml(sensor.sensorCode)}</small>
            </span>
          </td>
          <td>${escapeHtml(sensor.category || "Uncategorized")}</td>
          <td>${escapeHtml(sensorUnit(sensor))}</td>
        </tr>`;
    })
    .join("");

  if (rows.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="4" class="sensor-average-empty">No sensors match these filters.</td>
      </tr>`;
  }

  if (pickerResultCount) {
    const first = filtered.length ? start + 1 : 0;
    const last = Math.min(start + rows.length, filtered.length);
    pickerResultCount.textContent =
      filtered.length === sensors.length
        ? `Showing ${first}–${last} of ${sensors.length} sensors`
        : `Showing ${first}–${last} of ${filtered.length} matching sensors`;
  }
  if (pickerPageText) pickerPageText.textContent = `Page ${pickerPage} of ${pageCount}`;
  if (pickerPrevious) pickerPrevious.disabled = pickerPage <= 1;
  if (pickerNext) pickerNext.disabled = pickerPage >= pageCount;
  if (selectPageButton) selectPageButton.disabled = rows.length === 0;
  updateSelectionSummary();
}

function setPickerOpen(isOpen) {
  if (!pickerPanel || !pickerToggle) return;
  pickerPanel.hidden = !isOpen;
  pickerToggle.setAttribute("aria-expanded", String(isOpen));
  pickerToggle.textContent = isOpen ? "Hide sensor picker" : "Choose sensors";
  if (isOpen) renderPicker();
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
  if (chartPagination) chartPagination.hidden = true;
}

function clearCalculatedResults(message) {
  averagesByCode.clear();
  chartPage = 1;
  hideAverageChart();
  if (message) setStatus(message);
}

function invalidateResultsAfterSelectionChange() {
  if (averagesByCode.size === 0) return;
  clearCalculatedResults("Sensor selection changed. Calculate again to update the graph.");
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
    .sort((left, right) => right[1].length - left[1].length || left[0].localeCompare(right[0]))
    .map(([unit]) => unit);

  chartUnitSelect.innerHTML = units
    .map((unit) => `<option value="${escapeHtml(unit)}">${escapeHtml(unit)}</option>`)
    .join("");
  if (units.includes(previousUnit)) chartUnitSelect.value = previousUnit;
  if (chartUnitControl) chartUnitControl.hidden = units.length <= 1;
  return chartUnitSelect.value || units[0] || null;
}

function sortChartRows(rows) {
  const mode = chartSortSelect?.value || "name";
  return [...rows].sort((left, right) => {
    if (mode === "high") return Number(right.averageValue) - Number(left.averageValue);
    if (mode === "low") return Number(left.averageValue) - Number(right.averageValue);
    return sensorName(left).localeCompare(sensorName(right));
  });
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
  if (chartPagination) chartPagination.hidden = true;
}

function chartLabel(result) {
  const name = sensorName(result);
  const shortName = name.length > 34 ? `${name.slice(0, 31)}…` : name;
  return `${result.sensorCode} · ${shortName}`;
}

function renderAverageChart() {
  if (!chartCanvas || !chartPanel) return;
  const ChartConstructor = window.Chart;
  if (typeof ChartConstructor !== "function") {
    showChartEmpty("The graph library did not load. Check the internet connection and refresh.");
    return;
  }

  const groupedResults = resultsGroupedByUnit();
  const selectedUnit = updateUnitOptions(groupedResults);
  if (!selectedUnit) {
    showChartEmpty("No numeric readings were available for the selected sensors.");
    return;
  }

  const allRows = sortChartRows(groupedResults.get(selectedUnit) || []);
  if (allRows.length === 0) {
    showChartEmpty(`No numeric readings were available in ${selectedUnit}.`);
    return;
  }

  const pageCount = Math.max(1, Math.ceil(allRows.length / CHART_PAGE_SIZE));
  chartPage = Math.min(Math.max(1, chartPage), pageCount);
  const start = (chartPage - 1) * CHART_PAGE_SIZE;
  const rows = allRows.slice(start, start + CHART_PAGE_SIZE);

  destroyAverageChart();
  chartPanel.hidden = false;
  chartCanvas.hidden = false;
  if (chartEmpty) chartEmpty.hidden = true;
  if (chartFrame) chartFrame.style.height = `${Math.max(320, rows.length * 42 + 100)}px`;

  const groupedSensorCount = Array.from(groupedResults.values()).reduce(
    (total, group) => total + group.length,
    0
  );
  const excludedCount = selectedCodes.size - groupedSensorCount;
  const first = start + 1;
  const last = Math.min(start + rows.length, allRows.length);
  const excludedText = excludedCount
    ? ` ${excludedCount} selected sensor(s) had no numeric readings in this date range.`
    : "";
  if (chartSummary) {
    chartSummary.textContent = `Showing bars ${first}–${last} of ${allRows.length} in ${selectedUnit}.${excludedText}`;
  }

  if (chartPagination) chartPagination.hidden = pageCount <= 1;
  if (chartPageText) chartPageText.textContent = `Page ${chartPage} of ${pageCount}`;
  if (chartPrevious) chartPrevious.disabled = chartPage <= 1;
  if (chartNext) chartNext.disabled = chartPage >= pageCount;

  const theme = chartTheme();
  averageChart = new ChartConstructor(chartCanvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: rows.map(chartLabel),
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
      animation: rows.length <= 12,
      interaction: { mode: "nearest", intersect: true },
      scales: {
        x: {
          beginAtZero: false,
          title: {
            display: true,
            text: `Average reading (${selectedUnit})`,
            color: theme.text,
            font: { weight: "bold" },
          },
          ticks: { color: theme.muted, callback: (value) => formatNumber(value) },
          grid: { color: theme.grid },
        },
        y: {
          ticks: { color: theme.text, autoSkip: false, font: { size: 11 } },
          grid: { display: false },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => {
              const result = rows[items[0]?.dataIndex];
              return result ? [sensorName(result), result.sensorCode] : [];
            },
            label: (item) => `Average: ${formatNumber(item.raw)} ${selectedUnit}`,
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
    setPickerOpen(true);
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
  setStatus(`Calculating averages for ${selectedCodes.size} selected sensor(s)…`, "loading");

  try {
    const response = await apiRequest("/sensors/averages", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        sensorCodes: Array.from(selectedCodes),
        start: range.start,
        end: range.end,
      }),
    });
    const payload = await response.json();

    averagesByCode.clear();
    payload.sensors.forEach((result) => averagesByCode.set(result.sensorCode, result));
    chartPage = 1;
    setPickerOpen(false);
    renderAverageChart();

    const dateDescription =
      range.start || range.end ? "within the selected date range" : "across all imported readings";
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
    sensors.sort((left, right) => sensorName(left).localeCompare(sensorName(right)));
    populateFilterOptions();
    renderPicker();
    setStatus(
      `${sensors.length} sensors are available. Open the sensor picker to search and select them.`
    );
  } catch (error) {
    console.error("Could not load sensors for averages:", error);
    setStatus(error.message || "Could not load the sensor list.", "error");
    tableBody.innerHTML = `
      <tr><td colspan="4" class="sensor-average-empty">Could not load sensors from the API.</td></tr>`;
  }
}

function resetPickerToFirstPage() {
  pickerPage = 1;
  renderPicker();
}

pickerToggle?.addEventListener("click", () => setPickerOpen(pickerPanel?.hidden));
pickerClose?.addEventListener("click", () => setPickerOpen(false));

[searchInput, categoryFilter, unitFilter, selectedOnlyFilter].forEach((control) => {
  control?.addEventListener(control?.type === "search" ? "input" : "change", resetPickerToFirstPage);
});

clearFiltersButton?.addEventListener("click", () => {
  if (searchInput) searchInput.value = "";
  if (categoryFilter) categoryFilter.value = "";
  if (unitFilter) unitFilter.value = "";
  if (selectedOnlyFilter) selectedOnlyFilter.checked = false;
  resetPickerToFirstPage();
});

pickerPrevious?.addEventListener("click", () => {
  pickerPage -= 1;
  renderPicker();
});

pickerNext?.addEventListener("click", () => {
  pickerPage += 1;
  renderPicker();
});

selectPageButton?.addEventListener("click", () => {
  invalidateResultsAfterSelectionChange();
  pickerPageData().rows.forEach((sensor) => selectedCodes.add(sensor.sensorCode));
  renderPicker();
});

tableBody?.addEventListener("change", (event) => {
  const checkbox = event.target.closest(".sensor-average-checkbox");
  if (!checkbox) return;
  invalidateResultsAfterSelectionChange();
  if (checkbox.checked) selectedCodes.add(checkbox.value);
  else selectedCodes.delete(checkbox.value);
  renderPicker();
});

selectedPreview?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-average-sensor]");
  if (!button) return;
  invalidateResultsAfterSelectionChange();
  selectedCodes.delete(button.dataset.removeAverageSensor);
  renderPicker();
});

clearButton?.addEventListener("click", () => {
  selectedCodes.clear();
  averagesByCode.clear();
  hideAverageChart();
  renderPicker();
  setStatus("Selection cleared.");
});

calculateButton?.addEventListener("click", calculateAverages);

chartUnitSelect?.addEventListener("change", () => {
  chartPage = 1;
  renderAverageChart();
});
chartSortSelect?.addEventListener("change", () => {
  chartPage = 1;
  renderAverageChart();
});
chartPrevious?.addEventListener("click", () => {
  chartPage -= 1;
  renderAverageChart();
});
chartNext?.addEventListener("click", () => {
  chartPage += 1;
  renderAverageChart();
});

[startDateInput, endDateInput].forEach((input) => {
  input?.addEventListener("change", () => {
    clearCalculatedResults("Date range changed. Calculate again to update the graph.");
  });
});

new MutationObserver(() => {
  if (averagesByCode.size > 0) renderAverageChart();
}).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-theme"],
});

loadSensors();

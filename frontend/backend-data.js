function formatValue(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  return number.toLocaleString(undefined, {
    maximumFractionDigits: 2
  });
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return "No imported reading";
  }

  return new Date(timestamp).toLocaleString();
}

async function loadSensorsFromBackend() {
  try {
    // Phase 2 returns metadata and latest readings in one database/API call.
    const apiSensors = await apiGet("/sensors?includeLatest=true");

    buildingSensors = apiSensors.map((sensor) => ({
      id: sensor.sensorCode,
      name: sensor.displayName,
      type: sensor.category || "Uncategorized",
      value: sensor.hasReadings ? formatValue(sensor.latestValue) : "—",
      unit: sensor.displayUnit || "Unconfirmed",
      location: sensor.location || "GBTAC building",
      status: sensor.hasReadings
        ? "Readings imported"
        : "No imported readings",
      updated: sensor.latestTimestamp
        ? formatTimestamp(sensor.latestTimestamp)
        : "Not imported yet",
      priority: sensor.priority
    }));

    updateSensorSummary();
    renderSensors();
  } catch (error) {
    console.error("Could not load sensors:", error);

    if (sensorResultCount) {
      sensorResultCount.textContent =
        "Could not connect to the Sensor Data Service.";
    }
  }
}

async function loadHistoricalDatasetTimestamp() {
  const timestampElement = document.getElementById(
    "dashboardDataTimestamp"
  );

  if (!timestampElement) {
    return;
  }

  try {
    const overview = await apiGet("/dashboard/overview");

    timestampElement.textContent = overview.latestDatasetTimestamp
      ? `Historical readings through ${formatTimestamp(
          overview.latestDatasetTimestamp
        )}`
      : "Historical dataset loaded; no readings imported yet";
  } catch (error) {
    console.error("Could not load dataset timestamp:", error);
    timestampElement.textContent = "Historical data prototype";
  }
}

function buildChartReadingsPath() {
  const startDate = document.getElementById("chartStartDate")?.value;
  const endDate = document.getElementById("chartEndDate")?.value;
  const interval =
    document.getElementById("chartInterval")?.value || "hour";
  const parameters = new URLSearchParams({
    interval,
    limit: "500"
  });

  if (startDate) {
    parameters.set("start", `${startDate}T00:00:00`);
  }

  if (endDate) {
    parameters.set("end", `${endDate}T23:59:59`);
  }

  return `/sensors/30000_TL342/readings?${parameters.toString()}`;
}

async function loadSiteConsumptionChart() {
  const chartCanvas = document.getElementById("energyChart");
  const statusElement = document.getElementById("chartFilterStatus");

  if (!chartCanvas || typeof Chart === "undefined") {
    return;
  }

  if (statusElement) {
    statusElement.textContent = "Loading historical readings…";
  }

  try {
    const data = await apiGet(buildChartReadingsPath());
    const existingChart = Chart.getChart(chartCanvas);

    if (existingChart) {
      existingChart.destroy();
    }

    const displayUnit = data.sensor.displayUnit || "Unconfirmed";

    new Chart(chartCanvas, {
      type: "line",
      data: {
        labels: data.points.map((point) =>
          new Date(point.timestamp).toLocaleString()
        ),
        datasets: [
          {
            label: `${data.sensor.displayName} (${displayUnit})`,
            // Scaling happens in the backend. Valid negative values remain.
            data: data.points.map((point) => Number(point.value)),
            borderColor: "#1E9DD1",
            backgroundColor: "rgba(30, 157, 209, 0.12)",
            tension: 0.3,
            pointRadius: data.interval === "raw" ? 1 : 2,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: "top"
          },
          tooltip: {
            callbacks: {
              label: (context) => {
                const point = data.points[context.dataIndex];
                const range =
                  point.minimumValue !== null &&
                  point.maximumValue !== null
                    ? `; range ${formatValue(point.minimumValue)}–${formatValue(
                        point.maximumValue
                      )} ${displayUnit}`
                    : "";

                return `${data.sensor.displayName}: ${formatValue(
                  context.parsed.y
                )} ${displayUnit}${range}`;
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              maxTicksLimit: 6,
              maxRotation: 0
            }
          },
          y: {
            title: {
              display: true,
              text: `${data.sensor.displayName} (${displayUnit})`
            },
            ticks: {
              callback: (value) => `${value} ${displayUnit}`
            }
          }
        }
      }
    });

    if (statusElement) {
      statusElement.textContent = `${data.pointCount} ${data.interval} point${
        data.pointCount === 1 ? "" : "s"
      } shown`;
    }
  } catch (error) {
    console.error("Could not load site consumption chart:", error);

    if (statusElement) {
      statusElement.textContent = error.message;
    }
  }
}

const applyChartFiltersButton = document.getElementById(
  "applyChartFilters"
);

if (applyChartFiltersButton) {
  applyChartFiltersButton.addEventListener("click", loadSiteConsumptionChart);
}

if (sensorTableBody) {
  loadSensorsFromBackend();
}

if (document.getElementById("energyChart")) {
  loadSiteConsumptionChart();
  loadHistoricalDatasetTimestamp();
}

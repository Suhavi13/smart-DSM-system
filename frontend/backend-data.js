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

function formatValueWithUnit(value, unit) {
  const formattedValue = formatValue(value);
  return formattedValue === "—" ? formattedValue : `${formattedValue}${unit}`;
}

async function loadSensorsFromBackend() {
  try {
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

function buildSensorReadingsPath({
  sensorCode,
  startInputId,
  endInputId,
  intervalInputId
}) {
  const startDate = document.getElementById(startInputId)?.value;
  const endDate = document.getElementById(endInputId)?.value;
  const interval =
    document.getElementById(intervalInputId)?.value || "hour";
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

  return `/sensors/${encodeURIComponent(
    sensorCode
  )}/readings?${parameters.toString()}`;
}

function buildIndoorConditionsPath() {
  const startDate = document.getElementById("conditionsStartDate")?.value;
  const endDate = document.getElementById("conditionsEndDate")?.value;
  const interval =
    document.getElementById("conditionsInterval")?.value || "hour";
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

  return `/dashboard/indoor-conditions?${parameters.toString()}`;
}

async function loadConditionsChart() {
  const chartCanvas = document.getElementById("conditionsChart");
  const statusElement = document.getElementById("conditionsFilterStatus");

  if (!chartCanvas || typeof Chart === "undefined") {
    return;
  }

  if (statusElement) {
    statusElement.textContent = "Loading historical readings…";
  }

  try {
    const data = await apiGet(buildIndoorConditionsPath());
    const existingChart = Chart.getChart(chartCanvas);

    if (existingChart) {
      existingChart.destroy();
    }

    const temperatureUnit = data.temperatureUnit || "°C";

    new Chart(chartCanvas, {
      type: "line",
      data: {
        labels: data.points.map((point) =>
          new Date(point.timestamp).toLocaleString()
        ),
        datasets: [
          {
            label: `Average indoor temperature (${temperatureUnit})`,
            data: data.points.map((point) =>
              Number(point.averageTemperatureC)
            ),
            borderColor: "#1E9DD1",
            backgroundColor: "rgba(30, 157, 209, 0.12)",
            tension: 0.3,
            pointRadius: data.interval === "raw" ? 1 : 2,
            spanGaps: true,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          legend: {
            display: true,
            position: "top"
          },
          tooltip: {
            callbacks: {
              label: (context) =>
                `${context.dataset.label}: ${formatValue(
                  context.parsed.y
                )} ${temperatureUnit}`,
              afterLabel: (context) => {
                const point = data.points[context.dataIndex];
                return [
                  `Sensor range: ${formatValue(
                    point.minimumTemperatureC
                  )}–${formatValue(
                    point.maximumTemperatureC
                  )} ${temperatureUnit}`,
                  `Sensors contributing: ${point.contributingSensorCount}`
                ];
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
              text: `Average temperature (${temperatureUnit})`
            },
            ticks: {
              callback: (value) => `${value} ${temperatureUnit}`
            }
          }
        }
      }
    });

    if (statusElement) {
      const missingText = data.missingTemperatureSensorCodes.length
        ? `; ${data.missingTemperatureSensorCodes.length} sensor(s) missing`
        : "";
      statusElement.textContent =
        `${data.pointCount} ${data.interval} point${
          data.pointCount === 1 ? "" : "s"
        } • ${data.availableTemperatureSensorCount}/` +
        `${data.configuredTemperatureSensorCount} temperature sensors` +
        missingText;
    }
  } catch (error) {
    console.error("Could not load conditions chart:", error);

    if (statusElement) {
      statusElement.textContent = error.message;
    }
  }
}

function buildEnergyConsumptionPath() {
  const startDate = document.getElementById("chartStartDate")?.value;
  const endDate = document.getElementById("chartEndDate")?.value;
  const interval =
    document.getElementById("chartInterval")?.value || "day";
  const limitsByInterval = {
    raw: "200",
    "15min": "192",
    hour: "168",
    day: "60"
  };
  const parameters = new URLSearchParams({
    interval,
    limit: limitsByInterval[interval] || "60"
  });

  if (startDate) {
    parameters.set("start", `${startDate}T00:00:00`);
  }

  if (endDate) {
    parameters.set("end", `${endDate}T23:59:59`);
  }

  return `/dashboard/energy-consumption?${parameters.toString()}`;
}

function selectedEnergyMetric() {
  const selection = document.getElementById("energyMetric")?.value || "kWh";

  if (selection === "Wh") {
    return {
      field: "energyWh",
      label: "Energy used",
      unit: "Wh",
      chartType: "bar"
    };
  }

  if (selection === "W") {
    return {
      field: "averageWatts",
      label: "Average demand",
      unit: "W",
      chartType: "line"
    };
  }

  return {
    field: "energyKwh",
    label: "Energy used",
    unit: "kWh",
    chartType: "bar"
  };
}

function energyChartLabel(timestamp, interval) {
  const date = new Date(timestamp);
  return interval === "day"
    ? date.toLocaleDateString()
    : date.toLocaleString();
}

function updateEnergySummary(data) {
  const valueElement = document.getElementById("summaryEnergyUsage");
  const noteElement = document.getElementById("summaryEnergyNote");
  const latestPoint = data.points[data.points.length - 1];

  if (!valueElement || !noteElement) {
    return;
  }

  if (!latestPoint) {
    valueElement.textContent = "—";
    noteElement.textContent = "No cumulative energy deltas available";
    return;
  }

  const useWh = Math.abs(Number(latestPoint.energyKwh)) < 1;
  valueElement.innerHTML = useWh
    ? `${formatValue(latestPoint.energyWh)}<span> Wh</span>`
    : `${formatValue(latestPoint.energyKwh)}<span> kWh</span>`;
  noteElement.textContent =
    `${data.interval} usage • ${formatValue(latestPoint.averageWatts)} W average`;
}

async function loadEnergyConsumptionChart() {
  const chartCanvas = document.getElementById("energyChart");
  const statusElement = document.getElementById("chartFilterStatus");

  if (!chartCanvas || typeof Chart === "undefined") {
    return;
  }

  if (statusElement) {
    statusElement.textContent = "Calculating energy deltas…";
  }

  try {
    const data = await apiGet(buildEnergyConsumptionPath());
    const existingChart = Chart.getChart(chartCanvas);
    const metric = selectedEnergyMetric();

    if (existingChart) {
      existingChart.destroy();
    }

    new Chart(chartCanvas, {
      type: metric.chartType,
      data: {
        labels: data.points.map((point) =>
          energyChartLabel(point.timestamp, data.interval)
        ),
        datasets: [
          {
            label: `${metric.label} (${metric.unit})`,
            data: data.points.map((point) => Number(point[metric.field])),
            borderColor: "#1E9DD1",
            backgroundColor:
              metric.chartType === "bar"
                ? "rgba(30, 157, 209, 0.72)"
                : "rgba(30, 157, 209, 0.12)",
            tension: 0.3,
            pointRadius: metric.chartType === "line" ? 2 : 0,
            fill: metric.chartType === "line",
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          legend: {
            display: true,
            position: "top"
          },
          tooltip: {
            callbacks: {
              label: (context) =>
                `${metric.label}: ${formatValue(context.parsed.y)} ${metric.unit}`,
              afterLabel: (context) => {
                const point = data.points[context.dataIndex];
                return [
                  `Energy: ${formatValue(point.energyWh)} Wh (${formatValue(
                    point.energyKwh
                  )} kWh)`,
                  `Average demand: ${formatValue(point.averageWatts)} W`,
                  `Measured duration: ${formatValue(point.durationHours)} h`,
                  `Reading changes combined: ${point.count}`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              maxTicksLimit: 8,
              maxRotation: 0
            }
          },
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: `${metric.label} (${metric.unit})`
            },
            ticks: {
              callback: (value) => `${formatValue(value)} ${metric.unit}`
            }
          }
        }
      }
    });

    updateEnergySummary(data);

    if (statusElement) {
      const skippedText = data.skippedCounterChanges
        ? ` • ${data.skippedCounterChanges} counter reversal(s) skipped`
        : "";
      statusElement.textContent =
        `${data.pointCount} ${data.interval} period${
          data.pointCount === 1 ? "" : "s"
        } • derived from ${data.sensor.sensorCode} cumulative ${data.sourceUnit}` +
        skippedText;
    }
  } catch (error) {
    console.error("Could not load energy consumption chart:", error);

    if (statusElement) {
      statusElement.textContent = error.message;
    }
  }
}

function weatherSymbolForCode(code) {
  const number = Number(code);

  if (number === 0) return "☀";
  if ([1, 2].includes(number)) return "🌤";
  if (number === 3) return "☁";
  if ([45, 48].includes(number)) return "🌫";
  if ([51, 53, 55, 56, 57].includes(number)) return "🌦";
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(number)) {
    return "🌧";
  }
  if ([71, 73, 75, 77, 85, 86].includes(number)) return "🌨";
  if ([95, 96, 99].includes(number)) return "⛈";
  return "☁";
}

function formatForecastDate(dateValue) {
  const date = new Date(`${dateValue}T12:00:00`);
  return date.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric"
  });
}

async function loadWeatherForecastChart() {
  const chartCanvas = document.getElementById("weatherForecastChart");
  const statusElement = document.getElementById("weatherApiStatus");

  if (!chartCanvas || typeof Chart === "undefined") {
    return;
  }

  if (statusElement) {
    statusElement.textContent = "Loading";
  }

  try {
    const data = await apiGet("/external/weather/forecast");
    const today = data.daily[0] || {};

    const summaryTemperature = document.getElementById(
      "summaryOutdoorTemperature"
    );
    const summaryHumidity = document.getElementById(
      "summaryOutdoorHumidity"
    );
    const summaryCondition = document.getElementById(
      "summaryOutdoorCondition"
    );
    const summaryCacheStatus = document.getElementById(
      "summaryWeatherCacheStatus"
    );

    if (summaryTemperature) {
      summaryTemperature.textContent = formatValueWithUnit(
        data.current.temperatureC,
        "°C"
      );
    }

    if (summaryHumidity) {
      summaryHumidity.textContent = formatValueWithUnit(
        data.current.humidityPercent,
        "%"
      );
    }

    if (summaryCondition) {
      summaryCondition.textContent =
        data.current.condition || "Unknown conditions";
    }

    if (summaryCacheStatus) {
      summaryCacheStatus.textContent = data.isStale
        ? "Last successful forecast (stale)"
        : data.cacheStatus === "hit"
          ? "Served from Redis cache"
          : data.cacheStatus === "miss"
            ? "Fresh from Open-Meteo"
            : "Live provider response";
      summaryCacheStatus.classList.toggle("warning-text", data.isStale);
    }

    document.getElementById("weatherSymbol").textContent =
      weatherSymbolForCode(data.current.weatherCode);
    document.getElementById("weatherCurrentTemperature").textContent =
      formatValueWithUnit(data.current.temperatureC, "°C");
    document.getElementById("weatherCurrentCondition").textContent =
      data.current.condition || "Unknown conditions";
    document.getElementById("weatherCurrentHumidity").textContent =
      formatValueWithUnit(data.current.humidityPercent, "%");
    document.getElementById("weatherTodayHigh").textContent =
      formatValueWithUnit(today.maximumTemperatureC, "°C");
    document.getElementById("weatherTodayLow").textContent =
      formatValueWithUnit(today.minimumTemperatureC, "°C");

    const retrievedAtElement = document.getElementById(
      "weatherRetrievedAt"
    );
    if (retrievedAtElement) {
      retrievedAtElement.textContent = data.retrievedAt
        ? ` Forecast timestamp: ${formatTimestamp(data.retrievedAt)}.`
        : "";
    }

    const existingChart = Chart.getChart(chartCanvas);
    if (existingChart) {
      existingChart.destroy();
    }

    new Chart(chartCanvas, {
      type: "line",
      data: {
        labels: data.daily.map((day) => formatForecastDate(day.date)),
        datasets: [
          {
            label: "Daily high (°C)",
            data: data.daily.map((day) => day.maximumTemperatureC),
            borderColor: "#C45A24",
            backgroundColor: "rgba(196, 90, 36, 0.10)",
            tension: 0.3,
            pointRadius: 3,
            fill: false
          },
          {
            label: "Daily low (°C)",
            data: data.daily.map((day) => day.minimumTemperatureC),
            borderColor: "#1E9DD1",
            backgroundColor: "rgba(30, 157, 209, 0.10)",
            tension: 0.3,
            pointRadius: 3,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          legend: {
            display: true,
            position: "top"
          },
          tooltip: {
            callbacks: {
              afterBody: (items) => {
                const day = data.daily[items[0].dataIndex];
                return [
                  day.condition,
                  `Precipitation probability: ${formatValue(
                    day.precipitationProbabilityPercent
                  )}%`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              maxRotation: 0
            }
          },
          y: {
            title: {
              display: true,
              text: "Outdoor temperature (°C)"
            },
            ticks: {
              callback: (value) => `${value} °C`
            }
          }
        }
      }
    });

    if (statusElement) {
      const cacheLabel =
        data.cacheStatus === "hit"
          ? "Redis cache"
          : data.cacheStatus === "stale"
            ? "Stale fallback"
            : data.cacheStatus === "miss"
              ? "Fresh"
              : "Live";
      statusElement.textContent = cacheLabel;
      statusElement.classList.toggle("warning-text", Boolean(data.isStale));
    }
  } catch (error) {
    console.error("Could not load weather forecast:", error);

    if (statusElement) {
      statusElement.textContent = "Unavailable";
    }

    const conditionElement = document.getElementById(
      "weatherCurrentCondition"
    );
    if (conditionElement) {
      conditionElement.textContent = error.message;
    }
  }
}

async function loadRecommendationPreview() {
  const titleElement = document.getElementById(
    "dashboardRecommendationTitle"
  );

  if (!titleElement) {
    return;
  }

  const descriptionElement = document.getElementById(
    "dashboardRecommendationDescription"
  );
  const priorityElement = document.getElementById(
    "dashboardRecommendationPriority"
  );
  const evidenceElement = document.getElementById(
    "dashboardRecommendationEvidence"
  );
  const countElement = document.getElementById(
    "dashboardRecommendationCount"
  );
  const noteElement = document.getElementById(
    "dashboardRecommendationNote"
  );

  try {
    const data = await apiGet("/recommendations");
    const firstRecommendation = data.recommendations?.[0];

    if (countElement) {
      countElement.textContent = String(data.recommendationCount);
    }

    if (noteElement) {
      noteElement.textContent =
        `${data.recommendationCount} of ${data.rulesEvaluated} rules triggered`;
    }

    if (!firstRecommendation) {
      titleElement.textContent = "No active recommendation";
      if (descriptionElement) {
        descriptionElement.textContent =
          "All configured rules are currently below their trigger thresholds.";
      }
      if (priorityElement) {
        priorityElement.textContent = "None";
      }
      if (evidenceElement) {
        evidenceElement.textContent = "3 rules evaluated";
      }
      return;
    }

    titleElement.textContent = firstRecommendation.title;

    if (descriptionElement) {
      descriptionElement.textContent = firstRecommendation.description;
    }

    if (priorityElement) {
      priorityElement.textContent = firstRecommendation.priority;
    }

    if (evidenceElement) {
      const evidenceLabels = (firstRecommendation.evidence || [])
        .map((item) => item.label)
        .slice(0, 2);
      evidenceElement.textContent =
        evidenceLabels.join(" + ") || "Rule evidence";
    }
  } catch (error) {
    console.error("Could not load recommendation preview:", error);
    titleElement.textContent = "Recommendation service unavailable";

    if (descriptionElement) {
      descriptionElement.textContent = error.message;
    }

    if (priorityElement) {
      priorityElement.textContent = "—";
    }

    if (evidenceElement) {
      evidenceElement.textContent = "API error";
    }

    if (countElement) {
      countElement.textContent = "—";
    }

    if (noteElement) {
      noteElement.textContent = "Could not evaluate rules";
    }
  }
}

const applyConditionsFiltersButton = document.getElementById(
  "applyConditionsFilters"
);

if (applyConditionsFiltersButton) {
  applyConditionsFiltersButton.addEventListener(
    "click",
    loadConditionsChart
  );
}

const applyChartFiltersButton = document.getElementById(
  "applyChartFilters"
);

if (applyChartFiltersButton) {
  applyChartFiltersButton.addEventListener(
    "click",
    loadEnergyConsumptionChart
  );
}

if (sensorTableBody) {
  loadSensorsFromBackend();
}

if (document.getElementById("conditionsChart")) {
  loadConditionsChart();
}

if (document.getElementById("energyChart")) {
  loadEnergyConsumptionChart();
  loadHistoricalDatasetTimestamp();
}

if (document.getElementById("weatherForecastChart")) {
  loadWeatherForecastChart();
}

if (document.getElementById("dashboardRecommendationTitle")) {
  loadRecommendationPreview();
}

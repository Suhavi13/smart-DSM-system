const SITE_CONSUMPTION_SENSOR_CODE =
  window.APP_CONFIG.SITE_CONSUMPTION_SENSOR_CODE || "30000_TL342";

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
  const statusElement = document.getElementById(
    "conditionsFilterStatus"
  );

  if (!chartCanvas || typeof Chart === "undefined") {
    return;
  }

  if (statusElement) {
    statusElement.textContent = "Calculating 31-sensor average…";
  }

  try {
    const data = await apiGet(buildIndoorConditionsPath());
    const existingChart = Chart.getChart(chartCanvas);

    if (existingChart) {
      existingChart.destroy();
    }

    const temperatureUnit = data.temperatureUnit || "°C";
    const co2Unit = data.co2Unit || "ppm";
    const hasCo2Data = data.points.some(
      (point) => Number.isFinite(Number(point.co2Ppm))
    );
    const datasets = [
      {
        label: `Average indoor + wall temperature (${temperatureUnit})`,
        data: data.points.map((point) =>
          Number(point.averageTemperatureC)
        ),
        borderColor: "#1E9DD1",
        backgroundColor: "rgba(30, 157, 209, 0.12)",
        yAxisID: "temperatureAxis",
        tension: 0.3,
        pointRadius: data.interval === "raw" ? 1 : 2,
        spanGaps: true,
        fill: true
      }
    ];

    if (hasCo2Data) {
      datasets.push({
        label: `CO₂ (${co2Unit})`,
        data: data.points.map((point) =>
          Number.isFinite(Number(point.co2Ppm))
            ? Number(point.co2Ppm)
            : null
        ),
        borderColor: "#5A0E6F",
        backgroundColor: "transparent",
        yAxisID: "airQualityAxis",
        tension: 0.3,
        pointRadius: data.interval === "raw" ? 1 : 2,
        spanGaps: true
      });
    }

    new Chart(chartCanvas, {
      type: "line",
      data: {
        labels: data.points.map((point) =>
          new Date(point.timestamp).toLocaleString()
        ),
        datasets
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
              label: (context) => {
                const unit =
                  context.dataset.yAxisID === "airQualityAxis"
                    ? co2Unit
                    : temperatureUnit;
                return `${context.dataset.label}: ${formatValue(
                  context.parsed.y
                )} ${unit}`;
              },
              afterLabel: (context) => {
                if (context.dataset.yAxisID !== "temperatureAxis") {
                  return "";
                }

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
          temperatureAxis: {
            type: "linear",
            position: "left",
            title: {
              display: true,
              text: `Average temperature (${temperatureUnit})`
            },
            ticks: {
              callback: (value) => `${value} ${temperatureUnit}`
            }
          },
          airQualityAxis: {
            type: "linear",
            position: "right",
            display: hasCo2Data,
            title: {
              display: hasCo2Data,
              text: `CO₂ (${co2Unit})`
            },
            ticks: {
              callback: (value) => `${value} ${co2Unit}`
            },
            grid: {
              drawOnChartArea: false
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

function buildSiteConsumptionReadingsPath() {
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

  return `/dashboard/site-consumption?${parameters.toString()}`;
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
    const data = await apiGet(buildSiteConsumptionReadingsPath());
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
    loadSiteConsumptionChart
  );
}

if (sensorTableBody) {
  loadSensorsFromBackend();
}

if (document.getElementById("conditionsChart")) {
  loadConditionsChart();
}

if (document.getElementById("energyChart")) {
  loadSiteConsumptionChart();
  loadHistoricalDatasetTimestamp();
}

if (document.getElementById("weatherForecastChart")) {
  loadWeatherForecastChart();
}

async function loadRecommendationPreview() {
  const preview = document.getElementById("dashboardRecommendationPreview");
  const countElement = document.getElementById("dashboardRecommendationCount");
  const noteElement = document.getElementById("dashboardRecommendationNote");

  if (!preview && !countElement) {
    return;
  }

  try {
    const payload = await apiGet("/recommendations");
    const recommendations = payload.recommendations || [];

    if (countElement) {
      countElement.textContent = String(payload.recommendationCount || 0);
    }

    if (noteElement) {
      noteElement.textContent = recommendations.length
        ? `${payload.evaluatedRuleCount} rules evaluated`
        : "No rule needs attention";
      noteElement.classList.toggle("warning-text", recommendations.length > 0);
      noteElement.classList.toggle("positive", recommendations.length === 0);
    }

    if (!preview) {
      return;
    }

    const category = document.getElementById("dashboardRecommendationCategory");
    const title = document.getElementById("dashboardRecommendationTitle");
    const description = document.getElementById(
      "dashboardRecommendationDescription"
    );
    const reason = document.getElementById("dashboardRecommendationReason");
    const rule = document.getElementById("dashboardRecommendationRule");
    const status = document.getElementById("dashboardRecommendationStatus");

    if (!recommendations.length) {
      if (category) category.textContent = "All clear";
      if (title) title.textContent = "No recommendation is currently triggered";
      if (description) {
        description.textContent =
          "The available sensor and weather evidence did not cross any configured rule threshold.";
      }
      if (reason) reason.textContent = "";
      if (rule) rule.textContent = `${payload.evaluatedRuleCount} evaluated`;
      if (status) status.textContent = "No action needed";
      return;
    }

    const recommendation = recommendations[0];
    if (category) category.textContent = recommendation.category;
    if (title) title.textContent = recommendation.title;
    if (description) description.textContent = recommendation.description;
    if (reason) reason.textContent = recommendation.reason;
    if (rule) rule.textContent = recommendation.ruleId;
    if (status) status.textContent = "Pending review";
  } catch (error) {
    console.error("Could not load recommendation preview:", error);

    if (countElement) countElement.textContent = "—";
    if (noteElement) {
      noteElement.textContent = "Recommendation service unavailable";
      noteElement.classList.add("warning-text");
    }

    const title = document.getElementById("dashboardRecommendationTitle");
    const description = document.getElementById(
      "dashboardRecommendationDescription"
    );
    const status = document.getElementById("dashboardRecommendationStatus");
    if (title) title.textContent = "Could not load recommendations";
    if (description) description.textContent = error.message;
    if (status) status.textContent = "Unavailable";
  }
}

if (document.getElementById("dashboardRecommendationPreview")) {
  loadRecommendationPreview();
}

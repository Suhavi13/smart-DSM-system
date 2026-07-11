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

async function getLatestReading(sensorCode) {
  try {
    const data = await apiGet(
      `/readings/${encodeURIComponent(sensorCode)}?limit=1`
    );

    return data.points?.[data.points.length - 1] || null;
  } catch {
    return null;
  }
}

async function loadSensorsFromBackend() {
  try {
    const apiSensors = await apiGet("/sensors");

    const sensorsWithReadings = await Promise.all(
      apiSensors.map(async (sensor) => {
        const latestReading = await getLatestReading(sensor.sensorCode);

        return {
          id: sensor.sensorCode,
          name: sensor.displayName,
          type: sensor.category || "Uncategorized",
          value: latestReading ? formatValue(latestReading.value) : "—",
          unit: "Raw value",
          location: "GBT Lab",
          status: latestReading ? "Imported" : "No data",
          updated: latestReading
            ? formatTimestamp(latestReading.timestamp)
            : "Not imported yet",
          priority: sensor.priority
        };
      })
    );

    buildingSensors = sensorsWithReadings;

    updateSensorSummary();
    renderSensors();
  } catch (error) {
    console.error("Could not load sensors:", error);

    if (sensorResultCount) {
      sensorResultCount.textContent =
        "Could not connect to the backend.";
    }
  }
}

async function loadSiteConsumptionChart() {
  const chartCanvas = document.getElementById("energyChart");

  if (!chartCanvas || typeof Chart === "undefined") {
    return;
  }

  try {
    const data = await apiGet(
      "/readings/30000_TL342?limit=200"
    );

    const existingChart = Chart.getChart(chartCanvas);

    if (existingChart) {
      existingChart.destroy();
    }

    new Chart(chartCanvas, {
      type: "line",
      data: {
        labels: data.points.map((point) =>
          new Date(point.timestamp).toLocaleString()
        ),
        datasets: [
          {
            label: "GBT Site Consumption (kW)",
            data: data.points.map((point) =>
              Math.abs(Number(point.value)) / 1000
            ),
            borderColor: "#1E9DD1",
            backgroundColor: "rgba(30, 157, 209, 0.12)",
            tension: 0.3,
            pointRadius: 1,
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
              label: (context) =>
                `Site Consumption: ${context.parsed.y.toFixed(2)} kW`
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
              text: "Site Consumption (kW)"
            },
            ticks: {
              callback: (value) => `${value} kW`
            }
          }
        }
      }
    });
  } catch (error) {
    console.error("Could not load site consumption chart:", error);
  }
}

if (sensorTableBody) {
  loadSensorsFromBackend();
}

if (document.getElementById("energyChart")) {
  loadSiteConsumptionChart();
}
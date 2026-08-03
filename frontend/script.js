// Shared page elements and persistent light/dark theme controls.
const themeToggles = document.querySelectorAll('[data-theme-toggle]');

// Applies the selected theme to the page and updates all theme toggle labels.
function applyTheme(theme) {
  const isDark = theme === 'dark';

  document.documentElement.dataset.theme = isDark ? 'dark' : 'light';
  document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';

  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = isDark ? '#b8c5d6' : '#64748B';
    Chart.defaults.borderColor = isDark ? '#334155' : '#E2E8F0';
  }

  themeToggles.forEach((toggle) => {
    const label = toggle.querySelector('.theme-toggle-label');
    const icon = toggle.querySelector('.theme-toggle-icon');

    toggle.setAttribute(
      'aria-label',
      `Switch to ${isDark ? 'light' : 'dark'} mode`
    );
    toggle.setAttribute('aria-pressed', String(isDark));

    if (label) {
      label.textContent = isDark ? 'Light mode' : 'Dark mode';
    }

    if (icon) {
      icon.textContent = isDark ? '☀' : '☾';
    }
  });
}

// Load the previously selected theme.
const savedTheme =
  localStorage.getItem('gbtacTheme') ||
  document.documentElement.dataset.theme ||
  'light';

applyTheme(savedTheme);

// Save the user's theme choice whenever they use a theme toggle.
themeToggles.forEach((toggle) => {
  toggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.dataset.theme;
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';

    localStorage.setItem('gbtacTheme', nextTheme);
    applyTheme(nextTheme);
  });
});

const sensorSearch = document.getElementById('sensorSearch');
const sensorFilterField = document.getElementById('sensorFilterField');
const sensorTableBody = document.getElementById('sensorTableBody');
const sensorResultCount = document.getElementById('sensorResultCount');
const totalSensors = document.getElementById('totalSensors');
const onlineSensors = document.getElementById('onlineSensors');
const offlineSensors = document.getElementById('offlineSensors');
const activeAlerts = document.getElementById('activeAlerts');
const currentYear = document.getElementById('currentYear');

// Sensor inventory state used by the Sensors page search and summary cards.
let buildingSensors = [];

// Allows data-loading scripts to provide the latest sensor list for rendering.
export function setBuildingSensors(nextSensors) {
  buildingSensors = Array.isArray(nextSensors) ? nextSensors : [];
}

const sensors = [
  {
    name: 'Temperature Sensor',
    value: '72°F',
    status: 'Normal',
    updated: '2 min ago',
  },
  {
    name: 'Airflow Sensor',
    value: '650 CFM',
    status: 'Warning',
    updated: '5 min ago',
  },
  {
    name: 'Damper Position Sensor',
    value: '65%',
    status: 'Critical',
    updated: '1 min ago',
  },
  {
    name: 'Return Air Sensor',
    value: '68°F',
    status: 'Normal',
    updated: '3 min ago',
  },
];

function getBadgeClass(status) {
  if (status === "Readings imported") return "badge badge-normal";
  if (status === "No data") return "badge badge-warning";
  if (status === "Online") return "badge badge-normal";
  if (status === "Offline") return "badge badge-critical";
  if (status === "Warning") return "badge badge-warning";
  if (status === "Critical") return "badge badge-critical";
  return "badge";
}

const sensorFilterFields = {
  id: ['id'],
  name: ['name'],
  type: ['type'],
  value: ['value'],
  unit: ['unit'],
  location: ['location'],
  status: ['status'],
  all: ['id', 'name', 'type', 'value', 'unit', 'location', 'status'],
};

// Rebuilds the sensor inventory table after search text or filter field changes.
function renderSensors(filter = '', filterField = 'all') {
  if (!sensorTableBody) return;
  const normalizedFilter = filter.trim().toLowerCase();
  const fields = sensorFilterFields[filterField] || sensorFilterFields.all;
  const filteredSensors = buildingSensors.filter((sensor) =>
    fields.map((field) => sensor[field])
      .some((value) => value.toLowerCase().includes(normalizedFilter))
  );
  sensorTableBody.innerHTML = filteredSensors
    .map(
      (sensor) => `
      <tr>
        <td><strong>${sensor.id}</strong></td>
        <td>${sensor.name}</td>
        <td>${sensor.type}</td>
        <td>${sensor.value}</td>
        <td>${sensor.unit}</td>
        <td>${sensor.location}</td>
        <td><span class="${getBadgeClass(sensor.status)}">${sensor.status}</span></td>
        <td>${sensor.updated}</td>
      </tr>`
    )
    .join('');
  if (sensorResultCount) sensorResultCount.textContent = `Showing ${filteredSensors.length} of ${buildingSensors.length} sensors`;
}

// Updates the summary cards shown above the sensor inventory table.
function updateSensorSummary() {
  if (totalSensors) {
    totalSensors.textContent = buildingSensors.length;
  }

  if (onlineSensors) {
    onlineSensors.textContent = buildingSensors.filter(
      (sensor) => sensor.status === "Readings imported"
    ).length;
  }

  if (offlineSensors) {
    offlineSensors.textContent = buildingSensors.filter(
      (sensor) => sensor.status === "No data"
    ).length;
  }

  if (activeAlerts) {
    activeAlerts.textContent = buildingSensors.filter(
      (sensor) => sensor.priority === "P1"
    ).length;
  }
}

if (currentYear) {
  currentYear.textContent = new Date().getFullYear();
}

// Render the sample temperature chart when Chart.js is available.
function initializeSensorChart() {
  const sensorTrendCanvas = document.getElementById('sensorTrendChart');
  if (typeof Chart === 'undefined' || !sensorTrendCanvas) return;

  new Chart(sensorTrendCanvas, {
    type: 'line',
    data: {
      labels: ['6 a.m.', '8 a.m.', '10 a.m.', '12 p.m.', '2 p.m.', '4 p.m.', '6 p.m.'],
      datasets: [{
        label: 'Lobby Temperature (C)',
        data: [20.8, 21.2, 21.7, 22.1, 22.6, 22.8, 22.4],
          borderColor: '#1E9DD1',
          backgroundColor: 'rgba(30, 157, 209, 0.12)',
          pointBackgroundColor: '#1E9DD1',
        pointRadius: 4,
        tension: 0.35,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      font: {
        family: 'Arial, Helvetica, sans-serif',
        size: 12,
        lineHeight: 1.2,
      },
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, border: { display: false } },
        y: {
          suggestedMin: 18,
          suggestedMax: 25,
          grid: { color: '#E2E8F0' },
          border: { display: false },
          ticks: { callback: (value) => `${value} C` },
        },
      },
    },
  });
}

initializeSensorChart();

// Wire up the Sensors page search box when those controls exist on the page.
if (sensorSearch) {
  updateSensorSummary();
  renderSensors();
  const updateSensorFilter = () => {
    renderSensors(sensorSearch.value, sensorFilterField ? sensorFilterField.value : 'all');
  };
  sensorSearch.addEventListener('input', updateSensorFilter);
  if (sensorFilterField) {
    sensorFilterField.addEventListener('change', updateSensorFilter);
  }
}

export { renderSensors, updateSensorSummary };

const loginForm = document.getElementById('loginForm');
const loginError = document.getElementById('loginError');
const signupForm = document.getElementById('signupForm');
const signupError = document.getElementById('signupError');
const showLogin = document.getElementById('showLogin');
const showSignup = document.getElementById('showSignup');
const forgotPassword = document.getElementById('forgotPassword');
const captchaChallenge = document.getElementById('captchaChallenge');
const captchaAnswer = document.getElementById('captchaAnswer');
const refreshCaptcha = document.getElementById('refreshCaptcha');
const sensorSearch = document.getElementById('sensorSearch');
const sensorFilterField = document.getElementById('sensorFilterField');
const sensorTableBody = document.getElementById('sensorTableBody');
const sensorResultCount = document.getElementById('sensorResultCount');
const totalSensors = document.getElementById('totalSensors');
const onlineSensors = document.getElementById('onlineSensors');
const offlineSensors = document.getElementById('offlineSensors');
const activeAlerts = document.getElementById('activeAlerts');
const currentUser = document.getElementById('currentUser');
const currentYear = document.getElementById('currentYear');
const recommendationList = document.getElementById('recommendationList');
const recommendationCount = document.getElementById('recommendationCount');
let captchaSolution = null;
let activeRecommendationDialog = null;

const recommendations = [
  { id: 'peak-demand', category: 'Demand', title: 'Peak demand reduction', description: 'Reduce HVAC cooling load between 4:00 p.m. and 6:00 p.m. to avoid peak electricity charges.', reason: 'Electricity pricing is expected to be high during peak hours.', savings: 85, priority: 'High' },
  { id: 'pre-cooling', category: 'HVAC', title: 'Pre-cooling strategy', description: 'Pre-cool the building before peak demand hours.', reason: 'Weather forecast shows high outdoor temperature later today.', savings: 120, priority: 'Medium' },
  { id: 'ventilation', category: 'Air quality', title: 'Ventilation optimization', description: 'Reduce ventilation slightly during low occupancy hours.', reason: 'CO2 levels are within the safe range and occupancy is low.', savings: 60, priority: 'Low' },
  { id: 'setpoint', category: 'HVAC', title: 'Setpoint adjustment', description: 'Increase cooling setpoint from 21 C to 22 C.', reason: 'Small setpoint changes can reduce HVAC energy use while maintaining comfort.', savings: 75, priority: 'Medium' },
  { id: 'lighting', category: 'Lighting', title: 'After-hours lighting schedule', description: 'Turn off nonessential lighting on levels 3 and 4 after 8:00 p.m.', reason: 'Occupancy data shows these floors are usually empty after business hours.', savings: 48, priority: 'Medium' },
  { id: 'equipment', category: 'Equipment', title: 'Stagger equipment start-up', description: 'Delay selected pumps and air handlers by 10-minute intervals during morning start-up.', reason: 'Simultaneous equipment start-up creates a short demand spike.', savings: 95, priority: 'High' },
  { id: 'economizer', category: 'HVAC', title: 'Enable economizer cooling', description: 'Use cooler outdoor air for morning cooling before mechanical chillers start.', reason: 'Outdoor temperature is below the indoor cooling target until 9:00 a.m.', savings: 105, priority: 'High' },
  { id: 'standby', category: 'Plug loads', title: 'Reduce standby loads', description: 'Power down idle meeting-room displays and shared equipment overnight.', reason: 'Standby consumption remains above the overnight baseline.', savings: 35, priority: 'Low' },
];

const buildingSensors = [
  { id: 'TMP-101', name: 'Lobby Temperature', type: 'Temperature', value: '22.4', unit: 'C', location: 'Main Lobby', status: 'Online', updated: '1 min ago' },
  { id: 'HUM-102', name: 'Lobby Humidity', type: 'Humidity', value: '42', unit: '%', location: 'Main Lobby', status: 'Online', updated: '2 min ago' },
  { id: 'CO2-201', name: 'East Wing CO2', type: 'CO2', value: '980', unit: 'ppm', location: 'East Wing', status: 'Warning', updated: '1 min ago' },
  { id: 'AIR-301', name: 'Supply Airflow', type: 'Airflow', value: '645', unit: 'CFM', location: 'AHU-1', status: 'Online', updated: '3 min ago' },
  { id: 'PRS-401', name: 'Duct Pressure', type: 'Pressure', value: '1.8', unit: 'in. w.g.', location: 'Mechanical Room', status: 'Online', updated: '2 min ago' },
  { id: 'DMP-501', name: 'Outside Air Damper', type: 'Damper Status', value: '65', unit: '% open', location: 'AHU-1', status: 'Warning', updated: '4 min ago' },
  { id: 'TMP-103', name: 'Server Room Temperature', type: 'Temperature', value: '20.1', unit: 'C', location: 'Server Room', status: 'Online', updated: '1 min ago' },
  { id: 'HUM-104', name: 'Archive Humidity', type: 'Humidity', value: '48', unit: '%', location: 'Archive Room', status: 'Offline', updated: '38 min ago' },
  { id: 'CO2-202', name: 'Conference Room CO2', type: 'CO2', value: '720', unit: 'ppm', location: 'Conference Room', status: 'Online', updated: '2 min ago' },
  { id: 'AIR-302', name: 'Return Airflow', type: 'Airflow', value: '590', unit: 'CFM', location: 'AHU-2', status: 'Online', updated: '5 min ago' },
  { id: 'PRS-402', name: 'Filter Differential Pressure', type: 'Pressure', value: '2.4', unit: 'in. w.g.', location: 'AHU-2', status: 'Warning', updated: '3 min ago' },
  { id: 'DMP-502', name: 'West Zone Damper', type: 'Damper Status', value: '0', unit: '% open', location: 'West Wing', status: 'Offline', updated: '52 min ago' },
];

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
  if (status === 'Online') return 'badge badge-normal';
  if (status === 'Offline') return 'badge badge-critical';
  if (status === 'Normal') return 'badge badge-normal';
  if (status === 'Warning') return 'badge badge-warning';
  if (status === 'Critical') return 'badge badge-critical';
  return 'badge';
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

function updateSensorSummary() {
  if (totalSensors) totalSensors.textContent = buildingSensors.length;
  if (onlineSensors) onlineSensors.textContent = buildingSensors.filter((sensor) => sensor.status === 'Online').length;
  if (offlineSensors) offlineSensors.textContent = buildingSensors.filter((sensor) => sensor.status === 'Offline').length;
  if (activeAlerts) activeAlerts.textContent = buildingSensors.filter((sensor) => sensor.status === 'Warning').length;
}

function getPasswordValidationMessage(password) {
  if (password.length < 8) return 'Password must be at least 8 characters long.';
  if (/\s/.test(password)) return 'Password cannot contain spaces.';
  if (!/[A-Z]/.test(password)) return 'Password must include at least 1 uppercase letter.';
  if (!/[a-z]/.test(password)) return 'Password must include at least 1 lowercase letter.';
  if (!/[0-9]/.test(password)) return 'Password must include at least 1 number.';
  if (!/[^A-Za-z0-9]/.test(password)) return 'Password must include at least 1 special character.';
  return '';
}

function updatePasswordRequirements(password) {
  const requirements = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
    spaces: !/\s/.test(password) && password.length > 0,
  };

  Object.entries(requirements).forEach(([name, isValid]) => {
    const item = document.querySelector(`[data-password-requirement="${name}"]`);
    if (!item) return;
    item.classList.toggle('is-valid', isValid);
  });
}

function generateCaptcha() {
  if (!captchaChallenge || !captchaAnswer) return;
  const letters = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
  captchaSolution = Array.from(
    { length: 6 },
    () => letters[Math.floor(Math.random() * letters.length)]
  ).join('');
  captchaChallenge.textContent = captchaSolution;
  captchaAnswer.value = '';
}

function showAuthForm(formName) {
  if (!loginForm || !signupForm) return;
  const isLogin = formName === 'login';
  loginForm.classList.toggle('is-hidden', !isLogin);
  signupForm.classList.toggle('is-hidden', isLogin);
  loginError.textContent = '';
  signupError.textContent = '';
}

function setupPasswordHoldToggles() {
  document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    const passwordInput = document.getElementById(button.dataset.passwordToggle);
    if (!passwordInput) return;

    const showPassword = () => {
      passwordInput.type = 'text';
    };

    const hidePassword = () => {
      passwordInput.type = 'password';
    };

    button.addEventListener('pointerdown', showPassword);
    button.addEventListener('pointerup', hidePassword);
    button.addEventListener('pointerleave', hidePassword);
    button.addEventListener('pointercancel', hidePassword);
    button.addEventListener('blur', hidePassword);
  });
}

function setupPasswordClipboardBlock() {
  document.querySelectorAll('input[type="password"]').forEach((input) => {
    ['copy', 'cut', 'paste'].forEach((eventName) => {
      input.addEventListener(eventName, (event) => {
        event.preventDefault();
      });
    });
  });
}

setupPasswordHoldToggles();
setupPasswordClipboardBlock();
generateCaptcha();

if (refreshCaptcha) {
  refreshCaptcha.addEventListener('click', () => {
    generateCaptcha();
    captchaAnswer.focus();
  });
}

const signupPasswordInput = document.getElementById('signupPassword');
if (signupPasswordInput) {
  updatePasswordRequirements(signupPasswordInput.value);
  signupPasswordInput.addEventListener('input', (event) => {
    updatePasswordRequirements(event.target.value);
  });
}

if (showLogin) {
  showLogin.addEventListener('click', () => {
    showAuthForm('login');
    generateCaptcha();
  });
}

if (showSignup) {
  showSignup.addEventListener('click', () => showAuthForm('signup'));
}

if (forgotPassword) {
  forgotPassword.addEventListener('click', () => {
    loginError.textContent = 'Please contact your administrator to reset your password.';
  });
}

if (signupForm) {
  signupForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const firstName = document.getElementById('signupFirstName').value.trim();
    const lastName = document.getElementById('signupLastName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    if (!firstName || !lastName || !email || !password || !confirmPassword) {
      signupError.textContent = 'Please complete all sign up fields.';
      return;
    }

    const passwordError = getPasswordValidationMessage(password);
    if (passwordError) {
      signupError.textContent = passwordError;
      return;
    }

    if (password !== confirmPassword) {
      signupError.textContent = 'Passwords do not match.';
      return;
    }

    signupError.textContent = '';
    document.getElementById('username').value = email;
    localStorage.setItem('gbtacCurrentUser', email);
    generateCaptcha();
    showAuthForm('login');
  });
}

if (loginForm) {
  loginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const captchaValue = captchaAnswer.value.trim().toUpperCase();

    if (!username || !password) {
      loginError.textContent = 'Please enter both username and password.';
      return;
    }

    if (!captchaAnswer.value || captchaValue !== captchaSolution) {
      loginError.textContent = 'Incorrect security check. Please try the new CAPTCHA.';
      generateCaptcha();
      captchaAnswer.focus();
      return;
    }

    localStorage.setItem('gbtacCurrentUser', username);
    window.location.href = 'dashboard.html';
  });
}

if (currentUser) {
  currentUser.textContent = localStorage.getItem('gbtacCurrentUser') || 'Operator';
}

if (currentYear) {
  currentYear.textContent = new Date().getFullYear();
}

function initializeDashboardCharts() {
  const conditionsCanvas = document.getElementById('conditionsChart');
  const energyCanvas = document.getElementById('energyChart');
  const weatherCanvas = document.getElementById('weatherForecastChart');
  if (typeof Chart === 'undefined') return;

  Chart.defaults.font.family = 'Arial, Helvetica, sans-serif';
  Chart.defaults.color = '#222222';

  const sharedOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'bottom',
        labels: { usePointStyle: true, boxWidth: 8, padding: 18 },
      },
    },
    scales: {
      x: { grid: { display: false }, border: { display: false } },
      y: { grid: { color: '#E2E8F0' }, border: { display: false } },
    },
  };

  if (conditionsCanvas) {
    new Chart(conditionsCanvas, {
      type: 'line',
      data: {
        labels: ['12 a.m.', '4 a.m.', '8 a.m.', '12 p.m.', '4 p.m.', '8 p.m.', 'Now'],
        datasets: [
          {
            label: 'Temperature (C)',
            data: [20.8, 20.4, 21.1, 22.2, 23.0, 22.7, 22.4],
            borderColor: '#1E9DD1',
            backgroundColor: 'rgba(30, 157, 209, 0.12)',
            tension: 0.35,
            pointRadius: 3,
            fill: true,
          },
          {
            label: 'Humidity (%)',
            data: [49, 50, 48, 45, 43, 45, 46],
            borderColor: '#5A0E6F',
            backgroundColor: 'transparent',
            tension: 0.35,
            pointRadius: 3,
          },
        ],
      },
      options: sharedOptions,
    });
  }

  if (energyCanvas) new Chart(energyCanvas, {
    type: 'bar',
    data: {
      labels: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
      datasets: [{
        label: 'Energy (kWh)',
        data: [312, 298, 325, 287, 274, 221, 205],
        backgroundColor: (context) => {
          const chart = context.chart;
          const { chartArea, ctx } = chart;
          if (!chartArea) return 'rgba(30, 157, 209, 0.72)';
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, 'rgba(30, 157, 209, 0.95)');
          gradient.addColorStop(1, 'rgba(30, 157, 209, 0.38)');
          return gradient;
        },
        hoverBackgroundColor: '#147EA9',
        borderColor: 'rgba(90, 14, 111, 0.38)',
        borderWidth: 1,
        borderRadius: { topLeft: 8, topRight: 8, bottomLeft: 2, bottomRight: 2 },
        barPercentage: 0.62,
        categoryPercentage: 0.72,
        maxBarThickness: 42,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: 'Daily energy usage',
          align: 'start',
          color: '#5A0E6F',
          font: { size: 14, weight: 800 },
          padding: { bottom: 10 },
        },
        tooltip: {
          backgroundColor: '#5A0E6F',
          titleColor: '#FFFFFF',
          bodyColor: '#FFFFFF',
          displayColors: false,
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (context) => `${context.parsed.y} kWh`,
          },
        },
      },
      layout: { padding: { top: 4, right: 8, bottom: 0, left: 0 } },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          title: {
            display: false,
            text: 'Day',
          },
          ticks: {
            color: '#64748B',
            font: { size: 11, weight: 700 },
            maxRotation: 0,
            minRotation: 0,
            callback: function(value) {
              return this.getLabelForValue(value).slice(0, 3);
            },
          },
        },
        y: {
          grid: { color: 'rgba(100, 116, 139, 0.16)' },
          border: { display: false },
          beginAtZero: true,
          suggestedMax: 360,
          title: {
            display: false,
            text: 'Energy usage (kWh)',
          },
          ticks: {
            color: '#64748B',
            padding: 6,
            maxTicksLimit: 5,
            callback: (value) => `${value}`,
          },
        },
      },
    },
  });

  if (weatherCanvas) {
    new Chart(weatherCanvas, {
      type: 'line',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{
          label: 'Forecast temperature (C)',
          data: [24, 26, 28, 29, 27, 25, 23],
          borderColor: '#1E9DD1',
          backgroundColor: 'rgba(30, 157, 209, 0.12)',
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: '#1E9DD1',
          fill: true,
        }],
      },
      options: {
        ...sharedOptions,
        plugins: { ...sharedOptions.plugins, legend: { display: false } },
        scales: {
          x: sharedOptions.scales.x,
          y: {
            ...sharedOptions.scales.y,
            suggestedMin: 18,
            suggestedMax: 30,
            ticks: { callback: (value) => `${value} C` },
          },
        },
      },
    });
  }
}

initializeDashboardCharts();

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

function renderRecommendations() {
  if (!recommendationList) return;
  recommendationList.innerHTML = recommendations.map((recommendation) => `
    <article class="recommendation-card" data-recommendation-id="${recommendation.id}">
      <div class="recommendation-main">
        <div>
          <span class="recommendation-category">${recommendation.category}</span>
          <h3>${recommendation.title}</h3>
        </div>
        <span class="priority priority-${recommendation.priority.toLowerCase()}">${recommendation.priority}</span>
      </div>
      <p class="recommendation-reason"><strong>Reason:</strong> ${recommendation.reason}</p>
      <div class="recommendation-meta">
        <span>Status: <strong class="recommendation-status status-pending">Pending review</strong></span>
      </div>
      <div class="recommendation-actions">
        <button type="button" class="btn recommendation-approve recommendation-action" data-action="approved">Approve</button>
        <button type="button" class="btn recommendation-reject recommendation-action" data-action="rejected">Reject</button>
      </div>
    </article>
  `).join('');

  if (recommendationCount) recommendationCount.textContent = recommendations.length;
}

renderRecommendations();

function showRecommendationDialog({ title, message, confirmText = 'OK', cancelText = null, type = 'info' }) {
  if (activeRecommendationDialog) {
    activeRecommendationDialog.remove();
    activeRecommendationDialog = null;
  }

  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'app-dialog-overlay';
    overlay.innerHTML = `
      <div class="app-dialog app-dialog-${type}" role="dialog" aria-modal="true" aria-labelledby="appDialogTitle" aria-describedby="appDialogMessage">
        <div class="app-dialog-icon" aria-hidden="true">${type === 'success' || type === 'reject-success' ? '&#10003;' : '!'}</div>
        <h2 id="appDialogTitle">${title}</h2>
        <p id="appDialogMessage">${message}</p>
        <div class="app-dialog-actions">
          ${cancelText ? `<button type="button" class="btn app-dialog-cancel">${cancelText}</button>` : ''}
          <button type="button" class="btn app-dialog-confirm">${confirmText}</button>
        </div>
      </div>
    `;

    const closeDialog = (result) => {
      overlay.remove();
      activeRecommendationDialog = null;
      resolve(result);
    };

    overlay.querySelector('.app-dialog-confirm').addEventListener('click', () => closeDialog(true));
    const cancelButton = overlay.querySelector('.app-dialog-cancel');
    if (cancelButton) {
      cancelButton.addEventListener('click', () => closeDialog(false));
    }
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay && cancelText) closeDialog(false);
    });
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeDialog(false);
    });

    document.body.appendChild(overlay);
    activeRecommendationDialog = overlay;
    overlay.querySelector('.app-dialog-confirm').focus();
  });
}

if (recommendationList) {
  recommendationList.addEventListener('click', async (event) => {
    const button = event.target.closest('.recommendation-action');
    if (!button) return;
    const card = button.closest('.recommendation-card');
    const status = card.querySelector('.recommendation-status');
    const isApproved = button.dataset.action === 'approved';
    const actionLabel = isApproved ? 'approve' : 'reject';
    const confirmed = await showRecommendationDialog({
      title: isApproved ? 'Approve recommendation?' : 'Reject recommendation?',
      message: `Are you sure you want to ${actionLabel} this recommendation?`,
      confirmText: isApproved ? 'Approve' : 'Reject',
      cancelText: 'Cancel',
      type: isApproved ? 'approve' : 'reject',
    });

    if (!confirmed) return;

    status.textContent = isApproved ? 'Approved' : 'Rejected';
    status.className = `recommendation-status ${isApproved ? 'status-approved' : 'status-rejected'}`;
    card.querySelectorAll('.recommendation-action').forEach((actionButton) => {
      actionButton.setAttribute('aria-pressed', String(actionButton === button));
    });
    await showRecommendationDialog({
      title: 'Success',
      message: `This recommendation has been ${isApproved ? 'approved' : 'rejected'} successfully.`,
      confirmText: 'OK',
      type: isApproved ? 'success' : 'reject-success',
    });
  });
}

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

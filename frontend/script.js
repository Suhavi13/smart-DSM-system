// Shared page elements and persistent light/dark theme controls.
const loginForm = document.getElementById('loginForm');
const themeToggles = document.querySelectorAll('[data-theme-toggle]');

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
    toggle.setAttribute('aria-label', `Switch to ${isDark ? 'light' : 'dark'} mode`);
    toggle.setAttribute('aria-pressed', String(isDark));
    if (label) label.textContent = isDark ? 'Light mode' : 'Dark mode';
    if (icon) icon.textContent = isDark ? '☀' : '☾';
  });
}

applyTheme(document.documentElement.dataset.theme || 'light');

themeToggles.forEach((toggle) => {
  toggle.addEventListener('click', () => {
    const nextTheme =
      document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('gbtacTheme', nextTheme);
    applyTheme(nextTheme);

    // Recreate charts so their canvas labels and grid lines use the new palette.
    if (document.querySelector('canvas') && typeof Chart !== 'undefined') {
      window.location.reload();
    }
  });
});

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
let captchaSolution = null;
const registeredUsersStorageKey = 'gbtacRegisteredUsers';

function getRegisteredUsers() {
  try {
    const users = JSON.parse(localStorage.getItem(registeredUsersStorageKey) || '[]');
    return Array.isArray(users) ? users : [];
  } catch {
    return [];
  }
}

async function hashPassword(password) {
  const passwordBytes = new TextEncoder().encode(password);
  const hashBuffer = await crypto.subtle.digest('SHA-256', passwordBytes);
  return Array.from(new Uint8Array(hashBuffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

// Sensor inventory state used by the Sensors page search and summary cards.
let buildingSensors = [];

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
  if (status === "Imported") return "badge badge-normal";
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
  if (totalSensors) {
    totalSensors.textContent = buildingSensors.length;
  }

  if (onlineSensors) {
    onlineSensors.textContent = buildingSensors.filter(
      (sensor) => sensor.status === "Imported"
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

function getPasswordValidationMessage(password) {
  if (password.length < 8) return 'Password must be at least 8 characters long.';
  if (/\s/.test(password)) return 'Password cannot contain spaces.';
  if (!/[A-Z]/.test(password)) return 'Password must include at least 1 uppercase letter.';
  if (!/[a-z]/.test(password)) return 'Password must include at least 1 lowercase letter.';
  if (!/[0-9]/.test(password)) return 'Password must include at least 1 number.';
  if (!/[^A-Za-z0-9]/.test(password)) return 'Password must include at least 1 special character.';
  return '';
}

// Keep the password checklist synchronized with the user's current input.
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

// Generate the six-character challenge used by the prototype login form.
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

// Switch between the login and account-registration forms.
function showAuthForm(formName) {
  if (!loginForm || !signupForm) return;
  const isLogin = formName === 'login';
  loginForm.classList.toggle('is-hidden', !isLogin);
  signupForm.classList.toggle('is-hidden', isLogin);
  loginError.textContent = '';
  signupError.textContent = '';
}

// Password visibility and clipboard protection handlers.
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

if (captchaChallenge) {
  captchaChallenge.addEventListener('copy', (event) => event.preventDefault());
}

if (captchaAnswer) {
  ['copy', 'cut', 'paste', 'drop'].forEach((eventName) => {
    captchaAnswer.addEventListener(eventName, (event) => event.preventDefault());
  });
}

// New visitors must create an account before they can log in.
if (loginForm && signupForm && getRegisteredUsers().length === 0) {
  showAuthForm('signup');
}

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
  signupForm.addEventListener('submit', async (event) => {
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

    const normalizedEmail = email.toLowerCase();
    const registeredUsers = getRegisteredUsers();
    if (registeredUsers.some((user) => user.email === normalizedEmail)) {
      signupError.textContent = 'An account with this email already exists. Please log in.';
      return;
    }

    registeredUsers.push({
      firstName,
      lastName,
      email: normalizedEmail,
      passwordHash: await hashPassword(password),
    });
    localStorage.setItem(registeredUsersStorageKey, JSON.stringify(registeredUsers));

    signupError.textContent = '';
    document.getElementById('username').value = normalizedEmail;
    signupForm.reset();
    updatePasswordRequirements('');
    generateCaptcha();
    showAuthForm('login');
    loginError.textContent = 'Account created successfully. Log in with your email and password.';
  });
}

if (loginForm) {
  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = document.getElementById('username').value.trim().toLowerCase();
    const password = document.getElementById('password').value;
    const captchaValue = captchaAnswer.value.trim().toUpperCase();

    if (!username || !password) {
      loginError.textContent = 'Please enter both username and password.';
      return;
    }

    const registeredUsers = getRegisteredUsers();
    if (registeredUsers.length === 0) {
      showAuthForm('signup');
      signupError.textContent = 'You need to sign up before you can log in.';
      return;
    }

    if (!captchaAnswer.value || captchaValue !== captchaSolution) {
      loginError.textContent = 'Incorrect security check. Please try the new CAPTCHA.';
      generateCaptcha();
      captchaAnswer.focus();
      return;
    }

    const passwordHash = await hashPassword(password);
    const account = registeredUsers.find(
      (user) => user.email === username && user.passwordHash === passwordHash
    );
    if (!account) {
      loginError.textContent = 'Invalid email or password. Please use the details created during sign up.';
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

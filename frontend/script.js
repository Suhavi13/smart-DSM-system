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
const sensorTypeFilter = document.getElementById('sensorTypeFilter');
const sensorStatusFilter = document.getElementById('sensorStatusFilter');
const sensorSortOrder = document.getElementById('sensorSortOrder');
const resetSensorInventoryFilters = document.getElementById('resetSensorInventoryFilters');
const sensorTableBody = document.getElementById('sensorTableBody');
const sensorResultCount = document.getElementById('sensorResultCount');
const sensorPageSummary = document.getElementById('sensorPageSummary');
const sensorPageIndicator = document.getElementById('sensorPageIndicator');
const sensorPreviousPage = document.getElementById('sensorPreviousPage');
const sensorNextPage = document.getElementById('sensorNextPage');
const totalSensors = document.getElementById('totalSensors');
const onlineSensors = document.getElementById('onlineSensors');
const offlineSensors = document.getElementById('offlineSensors');
const activeAlerts = document.getElementById('activeAlerts');
const currentYear = document.getElementById('currentYear');

const SENSOR_INVENTORY_PAGE_SIZE = 12;

// Sensor inventory state used by the Sensors page filters, pagination, and details.
let buildingSensors = [];
const sensorInventoryState = {
  query: '',
  type: '',
  status: '',
  sort: 'name',
  page: 1,
  expandedSensorIds: new Set(),
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function normalizeSensorText(value) {
  return String(value ?? '').trim().toLowerCase();
}

function hasImportedReadings(sensor) {
  const status = normalizeSensorText(sensor?.status);
  return status === 'readings imported' || status === 'available' || status === 'online';
}

function getSensorStatusLabel(sensor) {
  return hasImportedReadings(sensor) ? 'Available' : 'No data';
}

function getBadgeClass(status) {
  if (status === 'Readings imported' || status === 'Available' || status === 'Online') {
    return 'badge badge-normal';
  }
  if (status === 'No imported readings' || status === 'No data' || status === 'Warning') {
    return 'badge badge-warning';
  }
  if (status === 'Offline' || status === 'Critical') return 'badge badge-critical';
  return 'badge';
}

function syncSensorTypeFilter() {
  if (!sensorTypeFilter) return;

  const currentValue = sensorInventoryState.type;
  const types = [...new Set(
    buildingSensors
      .map((sensor) => String(sensor.type || 'Uncategorized').trim())
      .filter(Boolean)
  )].sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }));

  sensorTypeFilter.innerHTML = [
    '<option value="">All types</option>',
    ...types.map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`),
  ].join('');

  if (types.includes(currentValue)) {
    sensorTypeFilter.value = currentValue;
  } else {
    sensorInventoryState.type = '';
    sensorTypeFilter.value = '';
  }
}

// Allows data-loading scripts to provide the latest sensor list for rendering.
export function setBuildingSensors(nextSensors) {
  buildingSensors = Array.isArray(nextSensors) ? nextSensors : [];
  sensorInventoryState.page = 1;
  sensorInventoryState.expandedSensorIds.clear();
  syncSensorTypeFilter();
}

function getFilteredSensors() {
  const query = normalizeSensorText(sensorInventoryState.query);

  const filtered = buildingSensors.filter((sensor) => {
    const searchableValues = [
      sensor.id,
      sensor.name,
      sensor.type,
      sensor.value,
      sensor.unit,
      sensor.location,
      sensor.status,
      sensor.priority,
    ];

    const matchesQuery = !query || searchableValues.some((value) =>
      normalizeSensorText(value).includes(query)
    );
    const matchesType = !sensorInventoryState.type || sensor.type === sensorInventoryState.type;
    const matchesStatus = !sensorInventoryState.status
      || (sensorInventoryState.status === 'available' && hasImportedReadings(sensor))
      || (sensorInventoryState.status === 'missing' && !hasImportedReadings(sensor));

    return matchesQuery && matchesType && matchesStatus;
  });

  const sortKey = sensorInventoryState.sort;
  return filtered.sort((left, right) => {
    const leftValue = sortKey === 'id' ? left.id : sortKey === 'type' ? left.type : left.name;
    const rightValue = sortKey === 'id' ? right.id : sortKey === 'type' ? right.type : right.name;
    return String(leftValue || '').localeCompare(String(rightValue || ''), undefined, {
      numeric: true,
      sensitivity: 'base',
    });
  });
}

function buildSensorInventoryRows(pageSensors, pageStart) {
  if (!pageSensors.length) {
    return `
      <tr class="sensor-inventory-empty-row">
        <td colspan="6">
          <strong>No sensors match these filters.</strong>
          <span>Try clearing the search, type, or data-status filter.</span>
        </td>
      </tr>`;
  }

  return pageSensors.map((sensor, index) => {
    const sensorId = String(sensor.id ?? '');
    const isExpanded = sensorInventoryState.expandedSensorIds.has(sensorId);
    const detailId = `sensor-details-${pageStart + index}`;
    const readingAvailable = hasImportedReadings(sensor) && sensor.value !== '—';
    const statusLabel = getSensorStatusLabel(sensor);
    const rawStatus = String(sensor.status || statusLabel);

    return `
      <tr class="sensor-inventory-row">
        <td>
          <div class="sensor-identity">
            <strong>${escapeHtml(sensor.name || 'Unnamed sensor')}</strong>
            <span>${escapeHtml(sensorId || 'No sensor ID')}</span>
          </div>
        </td>
        <td class="sensor-type-column">${escapeHtml(sensor.type || 'Uncategorized')}</td>
        <td>
          <div class="sensor-reading ${readingAvailable ? '' : 'sensor-reading-empty'}">
            <strong>${readingAvailable ? escapeHtml(sensor.value) : '—'}</strong>
            <span>${readingAvailable ? escapeHtml(sensor.unit || '') : 'No imported reading'}</span>
          </div>
        </td>
        <td>
          <span class="${getBadgeClass(rawStatus)}" title="${escapeHtml(rawStatus)}">
            ${escapeHtml(statusLabel)}
          </span>
        </td>
        <td class="sensor-updated-column">
          <span class="sensor-updated-value">${escapeHtml(sensor.updated || 'Not available')}</span>
        </td>
        <td class="sensor-details-column">
          <button
            type="button"
            class="sensor-details-toggle"
            data-sensor-details="${escapeHtml(sensorId)}"
            aria-expanded="${isExpanded}"
            aria-controls="${detailId}"
          >
            ${isExpanded ? 'Hide' : 'Details'}
          </button>
        </td>
      </tr>
      <tr id="${detailId}" class="sensor-detail-row" ${isExpanded ? '' : 'hidden'}>
        <td colspan="6">
          <dl class="sensor-detail-grid">
            <div><dt>Location</dt><dd>${escapeHtml(sensor.location || 'Not specified')}</dd></div>
            <div><dt>Priority</dt><dd>${escapeHtml(sensor.priority || 'Not assigned')}</dd></div>
            <div><dt>Display unit</dt><dd>${escapeHtml(sensor.unit || 'Unconfirmed')}</dd></div>
            <div><dt>Sensor ID</dt><dd>${escapeHtml(sensorId || 'Not available')}</dd></div>
          </dl>
        </td>
      </tr>`;
  }).join('');
}

// Rebuilds the compact sensor inventory after filters or pagination change.
function renderSensors() {
  if (!sensorTableBody) return;

  const filteredSensors = getFilteredSensors();
  const pageCount = Math.max(1, Math.ceil(filteredSensors.length / SENSOR_INVENTORY_PAGE_SIZE));
  sensorInventoryState.page = Math.min(Math.max(sensorInventoryState.page, 1), pageCount);

  const pageStart = (sensorInventoryState.page - 1) * SENSOR_INVENTORY_PAGE_SIZE;
  const pageSensors = filteredSensors.slice(pageStart, pageStart + SENSOR_INVENTORY_PAGE_SIZE);
  const visibleStart = filteredSensors.length ? pageStart + 1 : 0;
  const visibleEnd = pageStart + pageSensors.length;
  const filtersActive = Boolean(
    sensorInventoryState.query || sensorInventoryState.type || sensorInventoryState.status
  );

  sensorTableBody.innerHTML = buildSensorInventoryRows(pageSensors, pageStart);

  if (sensorResultCount) {
    sensorResultCount.textContent = filtersActive
      ? `${filteredSensors.length} of ${buildingSensors.length} sensors match the filters`
      : `${buildingSensors.length} sensors available`;
  }
  if (sensorPageSummary) {
    sensorPageSummary.textContent = filteredSensors.length
      ? `Showing ${visibleStart}–${visibleEnd} of ${filteredSensors.length}`
      : 'Showing 0 sensors';
  }
  if (sensorPageIndicator) {
    sensorPageIndicator.textContent = `Page ${sensorInventoryState.page} of ${pageCount}`;
  }
  if (sensorPreviousPage) sensorPreviousPage.disabled = sensorInventoryState.page <= 1;
  if (sensorNextPage) sensorNextPage.disabled = sensorInventoryState.page >= pageCount;
}

// Updates the summary cards shown above the sensor inventory table.
function updateSensorSummary() {
  if (totalSensors) totalSensors.textContent = buildingSensors.length;
  if (onlineSensors) {
    onlineSensors.textContent = buildingSensors.filter(hasImportedReadings).length;
  }
  if (offlineSensors) {
    offlineSensors.textContent = buildingSensors.filter((sensor) => !hasImportedReadings(sensor)).length;
  }
  if (activeAlerts) {
    activeAlerts.textContent = buildingSensors.filter((sensor) => sensor.priority === 'P1').length;
  }
}

if (currentYear) {
  currentYear.textContent = new Date().getFullYear();
}

function updateSensorInventoryFromControls() {
  sensorInventoryState.query = sensorSearch?.value || '';
  sensorInventoryState.type = sensorTypeFilter?.value || '';
  sensorInventoryState.status = sensorStatusFilter?.value || '';
  sensorInventoryState.sort = sensorSortOrder?.value || 'name';
  sensorInventoryState.page = 1;
  renderSensors();
}

if (sensorTableBody) {
  sensorSearch?.addEventListener('input', updateSensorInventoryFromControls);
  sensorTypeFilter?.addEventListener('change', updateSensorInventoryFromControls);
  sensorStatusFilter?.addEventListener('change', updateSensorInventoryFromControls);
  sensorSortOrder?.addEventListener('change', updateSensorInventoryFromControls);

  resetSensorInventoryFilters?.addEventListener('click', () => {
    if (sensorSearch) sensorSearch.value = '';
    if (sensorTypeFilter) sensorTypeFilter.value = '';
    if (sensorStatusFilter) sensorStatusFilter.value = '';
    if (sensorSortOrder) sensorSortOrder.value = 'name';

    sensorInventoryState.query = '';
    sensorInventoryState.type = '';
    sensorInventoryState.status = '';
    sensorInventoryState.sort = 'name';
    sensorInventoryState.page = 1;
    sensorInventoryState.expandedSensorIds.clear();
    renderSensors();
  });

  sensorPreviousPage?.addEventListener('click', () => {
    sensorInventoryState.page -= 1;
    renderSensors();
  });

  sensorNextPage?.addEventListener('click', () => {
    sensorInventoryState.page += 1;
    renderSensors();
  });

  sensorTableBody.addEventListener('click', (event) => {
    const button = event.target.closest('[data-sensor-details]');
    if (!button) return;

    const sensorId = button.dataset.sensorDetails || '';
    if (sensorInventoryState.expandedSensorIds.has(sensorId)) {
      sensorInventoryState.expandedSensorIds.delete(sensorId);
    } else {
      sensorInventoryState.expandedSensorIds.add(sensorId);
    }
    renderSensors();
  });

  renderSensors();
}

export { renderSensors, updateSensorSummary };

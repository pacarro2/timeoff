const calendarEl = document.getElementById("calendar");
const addRangeBtn = document.getElementById("add-range");
const selectedRangeEl = document.getElementById("selected-range");
const rangesEl = document.getElementById("ranges");
const inputs = {
  ptoToday: document.getElementById("pto-today"),
  accrualRate: document.getElementById("accrual-rate"),
  schedule: document.getElementById("schedule"),
  nextPayDate: document.getElementById("next-pay-date"),
  includeWeekends: document.getElementById("include-weekends"),
};

const state = {
  viewDate: new Date(),
  selectedStart: null,
  selectedEnd: null,
  ranges: [],
  balances: {},
};

const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const STORAGE_KEY = "pto-forecast-state";

function toISODate(date) {
  return date.toISOString().split("T")[0];
}

function parseISODate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function sameDay(a, b) {
  return a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function inRange(date, start, end) {
  if (!start || !end) return false;
  return date >= start && date <= end;
}

function rangeOverlaps(date, ranges) {
  return ranges.some((range) => date >= range.start && date <= range.end);
}

function formatDisplay(date) {
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function listDates(start, end) {
  const dates = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    dates.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return dates;
}

function saveState() {
  const payload = {
    inputs: {
      ptoToday: inputs.ptoToday.value,
      accrualRate: inputs.accrualRate.value,
      schedule: inputs.schedule.value,
      nextPayDate: inputs.nextPayDate.value,
      includeWeekends: inputs.includeWeekends.checked,
    },
    viewDate: toISODate(new Date(state.viewDate)),
    ranges: state.ranges.map((range) => ({
      start: toISODate(range.start),
      end: toISODate(range.end),
      defaultHours: range.defaultHours,
      overrides: range.overrides,
    })),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;
  try {
    const payload = JSON.parse(raw);
    if (payload.inputs) {
      inputs.ptoToday.value = payload.inputs.ptoToday ?? inputs.ptoToday.value;
      inputs.accrualRate.value = payload.inputs.accrualRate ?? inputs.accrualRate.value;
      inputs.schedule.value = payload.inputs.schedule ?? inputs.schedule.value;
      inputs.nextPayDate.value = payload.inputs.nextPayDate ?? inputs.nextPayDate.value;
      inputs.includeWeekends.checked = Boolean(payload.inputs.includeWeekends);
    }
    if (payload.viewDate) {
      state.viewDate = parseISODate(payload.viewDate);
    }
    if (Array.isArray(payload.ranges)) {
      state.ranges = payload.ranges.map((range) => ({
        start: parseISODate(range.start),
        end: parseISODate(range.end),
        defaultHours: Number(range.defaultHours ?? 8),
        overrides: range.overrides || {},
      }));
    }
  } catch (error) {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function renderMonth(monthDate) {
  const monthEl = document.createElement("div");
  monthEl.className = "month";

  const title = document.createElement("h3");
  title.textContent = monthDate.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  monthEl.appendChild(title);

  const weekdays = document.createElement("div");
  weekdays.className = "weekdays";
  dayNames.forEach((name) => {
    const span = document.createElement("span");
    span.textContent = name;
    weekdays.appendChild(span);
  });
  monthEl.appendChild(weekdays);

  const days = document.createElement("div");
  days.className = "days";
  const year = monthDate.getFullYear();
  const month = monthDate.getMonth();
  const firstDay = new Date(year, month, 1);
  const startWeekday = firstDay.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  for (let i = 0; i < startWeekday; i += 1) {
    const spacer = document.createElement("div");
    days.appendChild(spacer);
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(year, month, day);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "day";
    button.textContent = day;
    button.dataset.date = toISODate(date);

    if (date < today) {
      button.classList.add("disabled");
      button.disabled = true;
    }

    if (state.selectedStart && sameDay(date, state.selectedStart)) {
      button.classList.add("range-start");
    }
    if (state.selectedEnd && sameDay(date, state.selectedEnd)) {
      button.classList.add("range-end");
    }
    if (inRange(date, state.selectedStart, state.selectedEnd)) {
      button.classList.add("in-range");
    }
    if (rangeOverlaps(date, state.ranges)) {
      button.classList.add("booked");
    }

    const balance = state.balances[toISODate(date)];
    if (balance !== undefined) {
      const badge = document.createElement("span");
      badge.className = "day-balance";
      badge.textContent = `${balance.toFixed(1)}h`;
      button.appendChild(badge);
    }

    button.addEventListener("click", () => handleSelectDate(date));
    days.appendChild(button);
  }

  monthEl.appendChild(days);
  return monthEl;
}

function renderCalendar() {
  calendarEl.innerHTML = "";
  const firstMonth = new Date(state.viewDate.getFullYear(), state.viewDate.getMonth(), 1);
  const secondMonth = new Date(state.viewDate.getFullYear(), state.viewDate.getMonth() + 1, 1);
  calendarEl.appendChild(renderMonth(firstMonth));
  calendarEl.appendChild(renderMonth(secondMonth));
}

function updateSelectedLabel() {
  if (!state.selectedStart) {
    selectedRangeEl.textContent = "Choose a start date";
    return;
  }
  if (!state.selectedEnd) {
    selectedRangeEl.textContent = `${formatDisplay(state.selectedStart)} — choose an end date`;
    return;
  }
  selectedRangeEl.textContent = `${formatDisplay(state.selectedStart)} to ${formatDisplay(state.selectedEnd)}`;
}

function handleSelectDate(date) {
  if (!state.selectedStart || (state.selectedStart && state.selectedEnd)) {
    state.selectedStart = date;
    state.selectedEnd = null;
  } else if (date < state.selectedStart) {
    state.selectedEnd = state.selectedStart;
    state.selectedStart = date;
  } else {
    state.selectedEnd = date;
  }
  addRangeBtn.disabled = !(state.selectedStart && state.selectedEnd);
  updateSelectedLabel();
  renderCalendar();
}

function renderRanges() {
  rangesEl.innerHTML = "";
  if (!state.ranges.length) {
    rangesEl.textContent = "No trips added yet.";
    return;
  }
  state.ranges.forEach((range, index) => {
    const item = document.createElement("div");
    item.className = "range-item";
    const header = document.createElement("div");
    header.className = "range-header";
    const span = document.createElement("span");
    span.textContent = `${formatDisplay(range.start)} to ${formatDisplay(range.end)}`;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "link-button";
    toggle.textContent = "Edit days";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Remove";
    button.addEventListener("click", () => {
      state.ranges.splice(index, 1);
      renderRanges();
      renderCalendar();
      updateForecast();
    });
    header.appendChild(span);
    header.appendChild(toggle);
    header.appendChild(button);
    item.appendChild(header);

    const dayList = document.createElement("div");
    dayList.className = "range-days";
    dayList.hidden = true;
    listDates(range.start, range.end).forEach((date) => {
      const row = document.createElement("div");
      row.className = "range-day";
      const label = document.createElement("span");
      label.textContent = formatDisplay(date);
      if (date.getDay() === 0 || date.getDay() === 6) {
        label.classList.add("weekend");
      }
      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.step = "0.5";
      const iso = toISODate(date);
      const stored = range.overrides[iso];
      input.value = Number(stored === undefined ? range.defaultHours : stored).toFixed(1);
      input.setAttribute("aria-label", `Hours for ${label.textContent}`);
      const handleHoursChange = (event) => {
        const parsed = parseFloat(event.target.value);
        range.overrides[iso] = Number.isFinite(parsed) ? parsed : 0;
        updateForecast();
        saveState();
      };
      input.addEventListener("change", handleHoursChange);
      input.addEventListener("input", handleHoursChange);
      row.appendChild(label);
      row.appendChild(input);
      dayList.appendChild(row);
    });

    toggle.addEventListener("click", () => {
      dayList.hidden = !dayList.hidden;
      toggle.textContent = dayList.hidden ? "Edit days" : "Hide days";
    });

    item.appendChild(dayList);
    rangesEl.appendChild(item);
  });
  saveState();
}

function addRange() {
  if (!state.selectedStart || !state.selectedEnd) return;
  state.ranges.push({
    start: state.selectedStart,
    end: state.selectedEnd,
    defaultHours: 8,
    overrides: {},
  });
  state.selectedStart = null;
  state.selectedEnd = null;
  addRangeBtn.disabled = true;
  updateSelectedLabel();
  renderRanges();
  renderCalendar();
  updateForecast();
  saveState();
}

function updateForecast() {
  if (!inputs.nextPayDate.value) return;

  const endDate = new Date(state.viewDate.getFullYear(), state.viewDate.getMonth() + 2, 0);
  const dayHours = {};
  state.ranges.forEach((range) => {
    listDates(range.start, range.end).forEach((date) => {
      const iso = toISODate(date);
      const hours = range.overrides[iso];
      const resolved = Number(hours === undefined ? range.defaultHours : hours) || 0;
      dayHours[iso] = (dayHours[iso] || 0) + resolved;
    });
  });
  const payload = {
    pto_today: Number(inputs.ptoToday.value || 0),
    accrual_rate: Number(inputs.accrualRate.value || 0),
    schedule: inputs.schedule.value,
    next_pay_date: inputs.nextPayDate.value,
    end_date: toISODate(endDate),
    include_weekends: inputs.includeWeekends.checked,
    days: Object.entries(dayHours).map(([date, hours]) => ({
      date,
      hours,
    })),
  };

  fetch("/forecast", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((response) => response.json())
    .then((data) => {
      state.balances = data.balances || {};
      renderCalendar();
      saveState();
    })
    .catch(() => {
      state.balances = {};
      renderCalendar();
      saveState();
    });
}

function seedDates() {
  const today = new Date();
  const nextPay = new Date();
  nextPay.setDate(today.getDate() + 14);

  inputs.nextPayDate.value = toISODate(nextPay);
}

function handleNavigation() {
  document.getElementById("prev-month").addEventListener("click", () => {
    state.viewDate = new Date(state.viewDate.getFullYear(), state.viewDate.getMonth() - 1, 1);
    renderCalendar();
    updateForecast();
  });
  document.getElementById("next-month").addEventListener("click", () => {
    state.viewDate = new Date(state.viewDate.getFullYear(), state.viewDate.getMonth() + 1, 1);
    renderCalendar();
    updateForecast();
  });
}

function handleInputUpdates() {
  Object.values(inputs).forEach((input) => {
    input.addEventListener("change", updateForecast);
    input.addEventListener("input", updateForecast);
    input.addEventListener("change", saveState);
    input.addEventListener("input", saveState);
  });
}

seedDates();
loadState();
renderCalendar();
updateSelectedLabel();
renderRanges();
handleNavigation();
handleInputUpdates();
addRangeBtn.addEventListener("click", addRange);
updateForecast();

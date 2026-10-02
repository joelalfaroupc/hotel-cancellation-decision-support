const reservations = window.IDSS_RESERVATIONS || [];
const metadata = window.IDSS_METADATA || {};
const engineConfig = window.IDSS_ENGINE_CONFIG || {};
const state = {
  filter: "ALL",
  query: "",
  executed: new Set(),
  scheduledTasks: [],
  selectedDay: null,
  selectedMonth: null,
};

const riskColors = {
  BAJO: "var(--low)",
  MEDIO: "var(--medium)",
  ALTO: "var(--high)",
  CRITICO: "var(--critical)",
};

const riskOrder = ["CRITICO", "ALTO", "MEDIO", "BAJO"];
const monthOrder = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const euro = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const pct = new Intl.NumberFormat("es-ES", {
  style: "percent",
  maximumFractionDigits: 1,
});

function byId(id) {
  return document.getElementById(id);
}

function cleanText(value) {
  return String(value || "")
    .replace(/[\u{1F000}-\u{1FAFF}\u2600-\u27BF]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

function shortAction(value) {
  return cleanText(value)
    .replace(/^ALERTA:\s*/i, "")
    .replace(/^PRIORIDAD MAXIMA\s*[—-]\s*/i, "")
    .replace(/^CRITICO:\s*/i, "");
}

function displayActionTitle(action) {
  const text = shortAction(action);
  const lower = text.toLowerCase();
  if (lower.includes("inusual para este perfil")) return "Revisar manualmente esta reserva";
  if (lower.includes("investigar si hay insatisfaccion") || lower.includes("investigar si hay insatisfacción")) return "Comprobar experiencia previa en CRM";
  if (lower.includes("revisar y reforzar el acuerdo corporativo")) return "Revisar acuerdo corporativo";
  if (lower.includes("clasificado como corporativo")) return "Verificar si es una empresa nueva";
  return text;
}

function roomDescription(item) {
  const rooms = {
    A: "habitacion estandar",
    B: "habitacion basica o economica",
    C: "habitacion superior",
    D: "habitacion superior con mas capacidad",
    E: "habitacion familiar o amplia",
    F: "habitacion familiar superior",
    G: "suite o categoria premium",
    H: "suite superior",
    K: "habitacion especial asignada por disponibilidad",
  };
  const meals = {
    BB: "alojamiento con desayuno incluido",
    HB: "media pension",
    FB: "pension completa",
    SC: "solo alojamiento",
    Undefined: "regimen no especificado",
  };
  return {
    title: `Tipo ${item.room_type} - ${item.meal}`,
    detail: `Tipo ${item.room_type}: ${rooms[item.room_type] || "categoria interna del hotel"}. ${item.meal}: ${meals[item.meal] || "regimen de comida registrado en la reserva"}.`,
  };
}

function guestHistory(item) {
  if (item.previous_cancellations > 0) {
    return `${item.previous_cancellations} cancelacion(es) previa(s). No tratar como cliente nuevo: ya existe historial de cancelacion.`;
  }
  if (item.repeated_guest) {
    return "Cliente repetidor sin cancelaciones previas registradas.";
  }
  return "Sin cancelaciones previas registradas. Primera reserva o sin historial suficiente.";
}

function countryLabel(item) {
  const names = {
    PRT: "Portugal",
    GBR: "Reino Unido",
    ESP: "España",
    FRA: "Francia",
    DEU: "Alemania",
    ITA: "Italia",
    IRL: "Irlanda",
    BEL: "Belgica",
    BRA: "Brasil",
    NLD: "Paises Bajos",
    USA: "Estados Unidos",
    CHE: "Suiza",
    CN: "China",
  };
  const code = item.country || "N/D";
  return names[code] ? `${names[code]} (${code})` : code;
}

function mainRecommendation(item) {
  if (item.channels.includes("llamada")) {
    return "Contactar directamente para confirmar intencion de llegada.";
  }
  if (item.channels.includes("sms")) {
    return "Enviar recordatorio breve y facilitar confirmacion rapida.";
  }
  if (item.channels.includes("email")) {
    return "Enviar email personalizado con incentivo o condiciones claras.";
  }
  return "Revisar la reserva y dejar seguimiento preventivo.";
}

function operationalImpact(item) {
  if (item.risk_level === "CRITICO") {
    return "Confirmar si el cliente mantiene la reserva antes de perder margen de reaccion.";
  }
  if (item.risk_level === "ALTO") {
    return "Reducir incertidumbre y aumentar compromiso antes de la fecha de llegada.";
  }
  if (item.risk_level === "MEDIO") {
    return "Mantener seguimiento preventivo sin sobrecargar al equipo de recepcion.";
  }
  return "Dejar la reserva en seguimiento rutinario y actuar solo si aparecen nuevas señales.";
}

function summaryProblem(item) {
  const signals = [];
  if (item.lead_time >= 120) signals.push(`${item.lead_time} dias de antelacion`);
  if (item.previous_cancellations > 0) signals.push(`${item.previous_cancellations} cancelacion previa`);
  if (item.country_risk === "High") signals.push(`pais ${countryLabel(item)} con riesgo alto`);
  if (item.spend_total > 500) signals.push(`${euro.format(item.spend_total)} expuestos`);
  const detail = signals.length ? ` Señales: ${signals.join(", ")}.` : "";
  return `${item.risk_level} con ${pct.format(item.cancel_prob)} de probabilidad.${detail}`;
}

function explainSituation(item) {
  const parts = [
    `Esta reserva tiene ${pct.format(item.cancel_prob)} de probabilidad estimada de cancelacion.`,
    `Llega el ${item.arrival} y se hizo con ${item.lead_time} dias de antelacion.`,
  ];
  if (item.previous_cancellations > 0) {
    parts.push(`Hay ${item.previous_cancellations} cancelacion(es) previa(s) asociadas.`);
  }
  if (item.country_risk === "High") {
    parts.push(`El pais de origen (${countryLabel(item)}) esta marcado como riesgo alto en las reglas del IDSS.`);
  }
  if (item.spend_total > 500) {
    parts.push(`El valor economico expuesto es relevante: ${euro.format(item.spend_total)}.`);
  }
  return parts.join(" ");
}

function readableSignals(item) {
  return `Pais: ${countryLabel(item)} - riesgo pais ${item.country_risk} - ${item.special_requests} peticion(es) especial(es)`;
}

function activeRulesExplanation(item) {
  const cluster = cleanText(item.cluster || item.cluster_profile?.cluster || "");
  const profile = cleanText(item.profile || item.cluster_profile?.nombre || "perfil TLP");
  const suffix = cluster ? `cluster ${cluster}` : "clustering TLP";
  return `La recomendacion sale del perfil ${profile}, asignado por ${suffix}, y del nivel de riesgo calculado para la reserva.`;
}

function ruleName(rule) {
  if (typeof rule === "string") return cleanText(rule);
  return cleanText(rule?.nombre || rule?.name || "");
}

function ruleAction(rule) {
  if (typeof rule === "string") return "";
  return cleanText(rule?.accion || "");
}

function actionKind(action, item, index = 0) {
  const text = action.toLowerCase();
  if (text.includes("tarjeta") || text.includes("deposit") || text.includes("prepago") || text.includes("garantia")) return "garantia";
  if (text.includes("llamada") || text.includes("telefon")) return "llamada";
  if (text.includes("sms")) return "sms";
  if (text.includes("email")) return "email";
  const fallback = item.channels[index % Math.max(item.channels.length, 1)];
  if (fallback === "llamada" || fallback === "sms" || fallback === "email") return fallback;
  return "revision";
}

function actionLabel(kind) {
  return {
    llamada: "Llamada",
    email: "Email",
    sms: "SMS",
    garantia: "Garantia",
    revision: "Revision",
  }[kind];
}

function actionButtonText(kind) {
  return {
    llamada: "Preparar llamada",
    email: "Enviar email",
    sms: "Preparar SMS",
    garantia: "Solicitar garantia",
    revision: "Marcar para revisar",
  }[kind];
}

function actionExplanation(kind, item) {
  if (kind === "llamada") {
    return `Recomendado para una reserva ${item.risk_level.toLowerCase()}: permite confirmar intencion, resolver dudas y registrar la respuesta.`;
  }
  if (kind === "email") {
    return "Sirve para dejar constancia escrita, explicar condiciones y enviar una oferta o recordatorio personalizado.";
  }
  if (kind === "sms") {
    return "Sirve para pedir una confirmacion rapida con poca friccion antes de la fecha de llegada.";
  }
  if (kind === "garantia") {
    return "Sirve para reducir cancelaciones de ultimo momento cuando el riesgo o las reglas piden mas compromiso.";
  }
  return "Sirve para que el equipo revise el caso antes de aplicar una medida mas fuerte.";
}

function timingDays(item) {
  const matches = String(item.timing || "").match(/\d+/g) || [];
  return matches.map(Number).filter((value) => Number.isFinite(value));
}

function timingText(item) {
  const days = timingDays(item);
  if (!days.length) return "Programar cuando lo revise recepcion.";
  if (days.length === 1) return `Programar ${days[0]} dia(s) antes de la llegada.`;
  return `Programar ${days.join(" o ")} dias antes de la llegada.`;
}

function parseArrivalDate(item) {
  const date = new Date(item.arrival);
  return Number.isNaN(date.getTime()) ? null : date;
}

function scheduledDayFor(item) {
  const date = parseArrivalDate(item);
  const days = timingDays(item);
  if (!date || !days.length) return Number(String(item.arrival || "").match(/\d+/)?.[0] || 1);
  const scheduled = new Date(date);
  scheduled.setDate(scheduled.getDate() - days[0]);
  return scheduled.getDate();
}

function scheduledMonthFor(item) {
  const date = parseArrivalDate(item);
  const days = timingDays(item);
  if (!date || !days.length) return item.arrival_month;
  const scheduled = new Date(date);
  scheduled.setDate(scheduled.getDate() - days[0]);
  return monthOrder[scheduled.getMonth()] || item.arrival_month;
}

function formatScheduledTask(task) {
  return `${task.label} - ${task.bookingId}`;
}

function validEmail(value) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(value || "").trim());
}

function statusFor(item) {
  return state.executed.has(item.id) ? "Ejecutada" : item.status;
}

function riskClass(level) {
  return `risk-pill risk-${level}`;
}

function countBy(items, key) {
  return items.reduce((acc, item) => {
    const value = item[key] || "Sin clasificar";
    acc[value] = (acc[value] || 0) + 1;
    return acc;
  }, {});
}

function availableCalendarMonths() {
  const months = Array.from(new Set(reservations.map((item) => item.arrival_month).filter(Boolean)));
  return monthOrder.filter((month) => months.includes(month));
}

function monthLabel(month) {
  return {
    January: "Enero",
    February: "Febrero",
    March: "Marzo",
    April: "Abril",
    May: "Mayo",
    June: "Junio",
    July: "Julio",
    August: "Agosto",
    September: "Septiembre",
    October: "Octubre",
    November: "Noviembre",
    December: "Diciembre",
  }[month] || month;
}

function busiestMonth() {
  const counts = reservations.reduce((acc, item) => {
    const month = item.arrival_month;
    if (!month) return acc;
    acc[month] = (acc[month] || 0) + 1;
    return acc;
  }, {});
  return availableCalendarMonths().sort((left, right) => {
    const delta = (counts[right] || 0) - (counts[left] || 0);
    if (delta) return delta;
    return monthOrder.indexOf(left) - monthOrder.indexOf(right);
  })[0] || "January";
}

function summarize() {
  const total = reservations.length;
  const highRisk = reservations.filter((item) => ["ALTO", "CRITICO"].includes(item.risk_level));
  const avg = reservations.reduce((sum, item) => sum + item.cancel_prob, 0) / Math.max(total, 1);
  const exposed = highRisk.reduce((sum, item) => sum + item.spend_total, 0);

  byId("totalBookings").textContent = total;
  byId("highRiskCount").textContent = highRisk.length;
  byId("revenueAtRisk").textContent = euro.format(exposed);
  byId("avgProb").textContent = pct.format(avg);
  byId("pendingActions").textContent = total - state.executed.size;
  byId("riskMix").textContent = `${highRisk.length} reservas requieren intervencion prioritaria`;
  byId("riskTotal").textContent = `${total} reservas`;
}

function renderRiskChart() {
  const counts = countBy(reservations, "risk_level");
  const total = reservations.length || 1;
  let start = 0;
  const segments = riskOrder.map((risk) => {
    const value = counts[risk] || 0;
    const end = start + (value / total) * 100;
    const segment = `${riskColors[risk]} ${start}% ${end}%`;
    start = end;
    return segment;
  });

  const donut = byId("riskDonut");
  donut.style.background = `conic-gradient(${segments.join(", ")})`;
  donut.dataset.label = `${reservations.length}`;

  byId("riskLegend").innerHTML = riskOrder
    .map((risk) => {
      const value = counts[risk] || 0;
      return `
        <div class="legend-item">
          <span><i class="swatch" style="background:${riskColors[risk]}"></i>${risk}</span>
          <strong>${value}</strong>
        </div>
      `;
    })
    .join("");
}

function renderProfileBars() {
  const counts = Object.entries(countBy(reservations, "profile")).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...counts.map(([, value]) => value), 1);
  byId("profileBars").innerHTML = counts
    .map(([profile, value]) => {
      const width = Math.max(8, (value / max) * 100);
      const label = cleanText(profile);
      return `
        <div class="bar-row">
          <span class="bar-label" title="${label}">${label}</span>
          <span class="bar-track"><span class="bar-fill" style="width:${width}%"></span></span>
          <strong>${value}</strong>
        </div>
      `;
    })
    .join("");
}

function renderCalendar() {
  const currentMonth = state.selectedMonth || busiestMonth();
  state.selectedMonth = currentMonth;
  const byDay = reservations.reduce((acc, item) => {
    if (item.arrival_month !== currentMonth) return acc;
    const day = Number(String(item.arrival || "").match(/\d+/)?.[0] || 0);
    if (!day) return acc;
    if (!acc[day]) acc[day] = { total: 0, low: 0, medium: 0, high: 0, critical: 0 };
    acc[day].total += 1;
    if (item.risk_level === "BAJO") acc[day].low += 1;
    if (item.risk_level === "MEDIO") acc[day].medium += 1;
    if (["ALTO", "CRITICO"].includes(item.risk_level)) acc[day].high += 1;
    if (item.risk_level === "CRITICO") acc[day].critical += 1;
    return acc;
  }, {});

  state.scheduledTasks.forEach((task) => {
    if (task.month !== currentMonth) return;
    if (!byDay[task.day]) byDay[task.day] = { total: 0, low: 0, medium: 0, high: 0, critical: 0 };
    byDay[task.day].tasks = [...(byDay[task.day].tasks || []), task];
  });

  const criticalDays = Object.values(byDay).filter((day) => day.critical > 0).length;
  byId("calendarSummary").textContent = `${monthLabel(currentMonth)} · ${criticalDays} dias con riesgo critico`;
  renderCalendarMonthOptions();

  byId("riskCalendar").innerHTML = Array.from({ length: 31 }, (_, index) => {
    const day = index + 1;
    const info = byDay[day];
    let className = "calendar-day";
    if (info?.total) className += " has-arrivals";
    if (info?.low && !info?.medium && !info?.high && !info?.critical) className += " risk-low";
    if (info?.medium && !info?.high && !info?.critical) className += " risk-medium";
    if (info?.high) className += " has-risk risk-high";
    if (info?.critical) className += " risk-critical";
    if (state.selectedDay === day) className += " selected";
    return `
      <button class="${className}" type="button" data-calendar-day="${day}" title="${info ? `${info.total} reservas en ${monthLabel(currentMonth)}` : `Sin llegadas registradas en ${monthLabel(currentMonth)}`}">
        ${day}
        ${info ? `<small>${info.total}</small>` : ""}
        ${info?.tasks?.length ? `<span class="task-dot" aria-label="Tareas programadas"></span>` : ""}
      </button>
    `;
  }).join("");

  document.querySelectorAll("[data-calendar-day]").forEach((button) => {
    button.addEventListener("click", () => showCalendarDay(Number(button.dataset.calendarDay)));
  });

  if (state.selectedDay) {
    showCalendarDay(state.selectedDay, false);
  }
}

function showCalendarDay(day, rerender = true) {
  state.selectedDay = day;
  const currentMonth = state.selectedMonth || busiestMonth();
  const arrivals = reservations
    .filter((item) => item.arrival_month === currentMonth)
    .filter((item) => Number(String(item.arrival || "").match(/\d+/)?.[0] || 0) === day)
    .slice(0, 5);
  const tasks = state.scheduledTasks.filter((task) => task.month === currentMonth && task.day === day);
  const content = [
    `<strong>${day} ${monthLabel(currentMonth)}</strong>`,
    arrivals.length
      ? `<span>${arrivals.length} reserva(s) con llegada este dia:</span><ul>${arrivals.map((item) => `<li>${item.id} - ${cleanText(item.profile)} - ${item.risk_level}</li>`).join("")}</ul>`
      : "<span>No hay llegadas registradas este dia.</span>",
    tasks.length
      ? `<span>Tareas programadas:</span><ul>${tasks.map((task) => `<li>${formatScheduledTask(task)}</li>`).join("")}</ul>`
      : "<span>No hay llamadas/emails programados.</span>",
  ].join("");
  byId("calendarDetail").innerHTML = content;
  if (rerender) renderCalendar();
}

function renderCalendarMonthOptions() {
  const select = byId("calendarMonth");
  if (!select) return;
  const months = availableCalendarMonths();
  select.innerHTML = months.map((month) => `<option value="${month}">${monthLabel(month)}</option>`).join("");
  select.value = state.selectedMonth || months[0] || "January";
}

function filteredReservations() {
  const query = state.query.trim().toLowerCase();
  return reservations.filter((item) => {
    const passesFilter = state.filter === "ALL" || item.risk_level === state.filter;
    const searchable = [
      item.id,
      item.hotel,
      cleanText(item.profile),
      item.market_segment,
      item.distribution_channel,
      item.risk_level,
      item.country_risk,
      item.country,
      ...item.channels,
    ]
      .join(" ")
      .toLowerCase();
    return passesFilter && (!query || searchable.includes(query));
  });
}

function renderRows() {
  const rows = filteredReservations();
  byId("reservationRows").innerHTML = rows
    .map((item) => {
      const status = statusFor(item);
      const initial = item.hotel.includes("Resort") ? "R" : "C";
      const hotelClass = item.hotel.includes("Resort") ? "hotel-resort" : "hotel-city";
      const avatarClass = item.hotel.includes("Resort") ? "resort" : "city";
      return `
        <tr class="${hotelClass}" data-id="${item.id}">
          <td>
            <div class="booking-main">
              <span class="avatar ${avatarClass}" title="${item.hotel}">${initial}</span>
              <span>
                <strong>${item.id}</strong>
                <small>${item.hotel} - ${item.total_guests} huespedes - ${item.total_nights} noches</small>
              </span>
            </div>
          </td>
          <td>
            <strong>${cleanText(item.profile)}</strong>
            <div class="booking-meta">${item.market_segment} - ${item.distribution_channel}</div>
          </td>
          <td>
            <strong>${item.arrival}</strong>
            <div class="booking-meta">${item.lead_time} dias de antelacion</div>
          </td>
          <td>
            <span class="${riskClass(item.risk_level)}">${item.risk_level} - ${pct.format(item.cancel_prob)}</span>
          </td>
          <td>
            <strong>${euro.format(item.spend_total)}</strong>
            <div class="booking-meta">ADR ${euro.format(item.adr)}</div>
          </td>
          <td>
            <strong>${cleanText(item.deposit_type || "Unknown")}</strong>
          </td>
          <td>
            <span class="status-pill ${status === "Ejecutada" ? "done" : ""}">${status}</span>
          </td>
        </tr>
      `;
    })
    .join("");

  document.querySelectorAll("#reservationRows tr").forEach((row) => {
    row.addEventListener("click", () => openDetail(row.dataset.id));
  });
}

function renderDetailChips(title, values) {
  if (!values.length) return "";
  return `
    <h3 class="section-title">${title}</h3>
    <div class="pill-list">
      ${values.map((value) => `<span class="channel-pill">${cleanText(value)}</span>`).join("")}
    </div>
  `;
}

function openDetail(id) {
  const item = reservations.find((candidate) => candidate.id === id);
  if (!item) return;
  closeNewReservationDrawer();
  const status = statusFor(item);
  const drawer = byId("detailDrawer");
  const reasons = item.causes.map(cleanText).filter(Boolean);
  const actions = item.actions.map(shortAction).filter(Boolean);
  const roomInfo = roomDescription(item);
  byId("detailContent").innerHTML = `
    <article class="detail">
      <header class="detail-hero">
        <p class="eyebrow">Ficha de intervencion</p>
        <h2>${item.id} - ${item.hotel}</h2>
        <div class="pill-list">
          <span class="${riskClass(item.risk_level)}">${item.risk_level} - ${pct.format(item.cancel_prob)}</span>
          <span class="status-pill ${status === "Ejecutada" ? "done" : ""}">${status}</span>
        </div>
      </header>

      <section class="detail-summary">
        <div class="summary-card">
          <span>Que pasa</span>
          <strong>${summaryProblem(item)}</strong>
        </div>
        <div class="summary-card">
          <span>Que hacer</span>
          <strong>${mainRecommendation(item)}</strong>
        </div>
        <div class="summary-card">
          <span>Para que sirve</span>
          <strong>${operationalImpact(item)}</strong>
        </div>
      </section>

      <div class="detail-grid">
        <div class="info-card"><span>Perfil TLP</span><strong>${cleanText(item.profile)}</strong></div>
        <div class="info-card"><span>Llegada</span><strong>${item.arrival}</strong></div>
        <div class="info-card"><span>Valor estimado</span><strong>${euro.format(item.spend_total)}</strong></div>
        <div class="info-card"><span>Canal</span><strong>${item.market_segment} - ${item.distribution_channel}</strong></div>
        <div class="info-card"><span>Tipo deposito</span><strong>${cleanText(item.deposit_type || "Unknown")}</strong></div>
        <div class="info-card"><span>Estancia</span><strong>${item.total_nights} noches - ${item.total_guests} huespedes</strong></div>
        <div class="info-card"><span>Huesped</span><strong>${cleanText(item.guest_name || "No disponible")}</strong></div>
        <div class="info-card"><span>Email huesped</span><strong>${cleanText(item.guest_email || "No disponible")}</strong></div>
        <div class="info-card"><span>Habitacion y regimen</span><strong>${roomInfo.title}</strong><p>${roomInfo.detail}</p></div>
        <div class="info-card"><span>Historial</span><strong>${guestHistory(item)}</strong></div>
        <div class="info-card"><span>Origen de la reserva</span><strong>${readableSignals(item)}</strong><p>El pais procede de dataset_5000.csv; el nivel de riesgo pais procede de las variables preparadas para el IDSS.</p></div>
      </div>

      ${renderDetailChips("Canales recomendados", item.channels)}

      <section class="plan-panel">
        <h3>Lectura concreta del caso</h3>
        <p>${explainSituation(item)}</p>
        <ul class="reason-list">
          ${reasons.map((reason) => `<li>${reason}</li>`).join("")}
        </ul>
        <div class="rules-note">${activeRulesExplanation(item)}</div>
      </section>

      <h3 class="section-title">Opciones de actuacion</h3>
      <div class="action-list">
        ${actions
          .map(
            (action, index) => {
              const kind = actionKind(action, item, index);
              return `
              <div class="action-card">
                <span class="action-index">${index + 1}</span>
                <div>
                  <div class="action-card-header">
                    <strong>${displayActionTitle(action)}</strong>
                    <span class="action-type">${actionLabel(kind)}</span>
                  </div>
                  <p class="action-explain">${actionExplanation(kind, item)}</p>
                  <p class="muted">${timingText(item)} Se puede aplicar sola o combinada con otras opciones del plan.</p>
                  <div class="action-buttons">
                    <button class="option-btn primary" type="button" data-action-option="${index}" data-action-kind="${kind}">${actionButtonText(kind)}</button>
                    <button class="option-btn" type="button" data-action-option="${index}" data-action-kind="done">Marcar realizada</button>
                  </div>
                </div>
              </div>
            `;
            },
          )
          .join("")}
      </div>

      <button class="decision-btn" type="button" data-execute="${item.id}">
        Ejecutar todo el plan recomendado
      </button>
    </article>
  `;

  byId("detailContent").querySelector("[data-execute]").addEventListener("click", () => executeDecision(item.id));
  byId("detailContent").querySelectorAll("[data-action-option]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      simulateOption(item.id, Number(button.dataset.actionOption) + 1, button.dataset.actionKind);
    });
  });
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function buildEmailPayload(item) {
  return {
    booking_id: item.id,
    guest_email: item.guest_email,
    guest_name: item.guest_name || "Huesped",
    hotel: item.hotel,
    arrival: item.arrival,
    risk_level: item.risk_level,
    cancel_prob: item.cancel_prob,
    profile: item.profile,
    actions: item.actions || [],
    causes: item.causes || [],
  };
}

async function sendHighRiskEmail(item) {
  if (!["ALTO", "CRITICO"].includes(item.risk_level)) {
    showToast(`Reserva ${item.id}: el envio solo esta disponible para riesgo ALTO o CRITICO.`);
    return;
  }
  if (!validEmail(item.guest_email)) {
    showToast(`Reserva ${item.id}: falta un email valido del huesped.`);
    return;
  }

  showToast(`Reserva ${item.id}: enviando email a ${item.guest_email}...`);
  try {
    const response = await fetch("/api/high-risk-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildEmailPayload(item)),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.detail || "No se pudo enviar el email");
    }
    item.email_status = "Enviado";
    state.executed.add(item.id);
    summarize();
    renderRows();
    openDetail(item.id);
    showToast(`Reserva ${item.id}: email enviado a ${result.to || item.guest_email}.`);
  } catch (error) {
    showToast(`Reserva ${item.id}: ${error.message}`);
  }
}

async function simulateOption(id, optionNumber, kind) {
  const item = reservations.find((candidate) => candidate.id === id);
  const labels = {
    llamada: "llamada preparada",
    email: "email enviado",
    sms: "SMS preparado",
    garantia: "solicitud de garantia preparada",
    revision: "revision marcada",
    done: "accion marcada como realizada",
  };
  if (item && kind === "email") {
    await sendHighRiskEmail(item);
    return;
  }
  if (item && kind !== "done") {
    const day = scheduledDayFor(item);
    const month = scheduledMonthFor(item);
    state.scheduledTasks.push({
      bookingId: id,
      day,
      month,
      kind,
      label: `${actionButtonText(kind)} reserva ${id}`,
    });
    state.selectedMonth = month;
    state.selectedDay = day;
    renderCalendar();
    showCalendarDay(day, false);
    showToast(`Reserva ${id}: ${labels[kind] || "accion preparada"} y añadida al calendario el ${day} de ${monthLabel(month)}.`);
    return;
  }
  showToast(`Reserva ${id}: opcion ${optionNumber} - ${labels[kind] || "accion preparada"}.`);
}

function executeDecision(id) {
  state.executed.add(id);
  summarize();
  renderRows();
  const item = reservations.find((candidate) => candidate.id === id);
  showToast(`Decision ejecutada para ${id}: ${item.channels.join(" + ") || "canal operativo"} activado.`);
  openDetail(id);
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = cleanText(message);
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function monthWeek(month) {
  return {
    January: 2,
    February: 7,
    March: 11,
    April: 15,
    May: 19,
    June: 24,
    July: 28,
    August: 32,
    September: 36,
    October: 41,
    November: 45,
    December: 49,
  }[month] || 26;
}

function sigmoid(value) {
  return 1 / (1 + Math.exp(-value));
}

function modelFeatureValue(feature, row) {
  if (feature.startsWith("num__")) {
    const column = feature.replace("num__", "");
    const stats = engineConfig.model_numeric_stats?.[column] || { mean: 0, std: 1 };
    const raw = Number(row[column] || 0);
    return (raw - Number(stats.mean || 0)) / Number(stats.std || 1);
  }
  if (feature.startsWith("bin__")) {
    return Number(row[feature.replace("bin__", "")] || 0);
  }
  if (feature.startsWith("cat__")) {
    const raw = feature.replace("cat__", "");
    const columns = [
      "distribution_channel",
      "arrival_date_year",
      "arrival_date_month",
      "market_segment",
      "reserved_room_type",
      "customer_type",
      "country_risk",
      "gender_account",
      "hotel",
      "meal",
    ];
    const match = columns.find((column) => raw.startsWith(`${column}_`));
    if (!match) return 0;
    return String(row[match] || "") === raw.slice(match.length + 1) ? 1 : 0;
  }
  return 0;
}

function evalTree(node, vector) {
  if (Object.prototype.hasOwnProperty.call(node, "leaf")) return Number(node.leaf || 0);
  const value = vector[node.split] ?? 0;
  const nextId = value < Number(node.split_condition) ? node.yes : node.no;
  const next = node.children.find((child) => child.nodeid === nextId) || node.children[0];
  return evalTree(next, vector);
}

function predictXgboostInBrowser(row) {
  const trees = engineConfig.xgboost_trees || [];
  const features = engineConfig.model_features || [];
  if (!trees.length || !features.length) return null;
  const vector = {};
  features.forEach((feature) => {
    vector[feature] = modelFeatureValue(feature, row);
  });
  const margin = trees.reduce((sum, tree) => sum + evalTree(tree, vector), 0);
  return Math.max(0, Math.min(1, sigmoid(margin)));
}

function clusterFeatureRow(row) {
  const spend = Number(row.adr_per_guest || 0) * Number(row.total_guests || 1) * Number(row.total_nights || 1);
  const maps = {
    meal_enc: { Undefined: 0, SC: 1, BB: 2, HB: 3, FB: 4 },
    segment_enc: { Groups: 0, Corporate: 1, "Offline TA/TO": 2, Direct: 3, "Online TA": 4 },
    ctype_enc: { Contract: 0, Group: 1, "Transient-Party": 2, Transient: 3 },
    risk_enc: { Low: 0, Medium: 1, High: 2 },
  };
  return {
    lead_time: Number(row.lead_time || 0),
    total_nights: Number(row.total_nights || 1),
    total_guests: Number(row.total_guests || 1),
    adr_per_guest: Number(row.adr_per_guest || 0),
    total_of_special_requests: Number(row.total_of_special_requests || 0),
    is_family_booking: Number(row.is_family_booking || 0),
    previous_cancellations: Number(row.previous_cancellations || 0),
    has_agent: Number(row.has_agent || 0),
    is_repeated_guest: Number(row.is_repeated_guest || 0),
    is_resort: row.hotel === "Resort Hotel" ? 1 : 0,
    meal_enc: maps.meal_enc[row.meal] ?? 1,
    segment_enc: maps.segment_enc[row.market_segment] ?? 2,
    ctype_enc: maps.ctype_enc[row.customer_type] ?? 3,
    risk_enc: maps.risk_enc[row.country_risk] ?? 1,
    spend_total: spend,
    booking_complexity: Number(row.total_of_special_requests || 0) + Number(row.is_family_booking || 0),
  };
}

function assignClusterInBrowser(row) {
  const features = engineConfig.cluster_features || [];
  const centroids = engineConfig.centroids || {};
  const values = clusterFeatureRow(row);
  let bestCluster = "4";
  let bestDistance = Number.POSITIVE_INFINITY;
  Object.entries(centroids).forEach(([cluster, centroid]) => {
    const distance = features.reduce((sum, feature, index) => {
      const mean = Number(engineConfig.cluster_means?.[feature] || 0);
      const std = Number(engineConfig.cluster_stds?.[feature] || 1);
      const scaled = (Number(values[feature] || 0) - mean) / std;
      return sum + (scaled - Number(centroid[index] || 0)) ** 2;
    }, 0);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestCluster = cluster;
    }
  });
  return {
    cluster: bestCluster,
    profile: engineConfig.profile_by_cluster?.[bestCluster] || "Viajero Estandar",
  };
}

function riskFromProbability(probability) {
  const thresholds = engineConfig.thresholds || {};
  const low = Number(thresholds.BAJO ?? 0.3);
  const high = Number(thresholds.ALTO ?? 0.55);
  let critical = Number(thresholds.CRITICO ?? 0.75);
  if (critical <= high) critical = Math.min(0.95, high + 0.15);
  if (probability >= critical) return "CRITICO";
  if (probability >= high) return "ALTO";
  if (probability >= low) return "MEDIO";
  return "BAJO";
}

function rulesForNewReservation(row, profile, risk) {
  const profileRules = engineConfig.profiles?.[profile] || engineConfig.profiles?.["Viajero Estandar"] || {};
  const riskRules = profileRules[risk] || profileRules.ALTO || {};
  const channels = [...(riskRules.canal || [])];
  const actions = [...(riskRules.acciones || [])];
  return {
    channels,
    actions,
    globalRules: [],
    timing: riskRules.timing_dias || [],
    priority: Number(riskRules.prioridad || 3),
    description: profileRules.descripcion || "",
  };
}

function buildNewReservation(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const totalGuests = Number(data.total_guests || 1);
  const totalNights = Number(data.total_nights || 1);
  const adr = Number(data.adr || 0);
  const row = {
    ...data,
    lead_time: Number(data.lead_time || 0),
    arrival_date_year: 2026,
    arrival_date_week_number: monthWeek(data.arrival_date_month),
    arrival_date_day_of_month: Number(data.arrival_date_day_of_month || 1),
    previous_cancellations: Number(data.previous_cancellations || 0),
    previous_bookings_not_canceled: 0,
    required_car_parking_spaces: 0,
    total_of_special_requests: Number(data.total_of_special_requests || 0),
    total_nights: totalNights,
    total_guests: totalGuests,
    adr,
    adr_per_guest: adr / Math.max(totalGuests, 1),
    has_agent: data.market_segment.includes("TA") ? 1 : 0,
    has_company: data.market_segment === "Corporate" ? 1 : 0,
    is_family_booking: totalGuests >= 3 ? 1 : 0,
    is_repeated_guest: 0,
    customer_type: data.market_segment === "Groups" ? "Transient-Party" : "Transient",
    country: "N/D",
  };
  row.spend_total = row.adr_per_guest * row.total_guests * row.total_nights;
  row.cancel_prob = predictXgboostInBrowser(row) ?? 0.5;
  row.risk_level = riskFromProbability(row.cancel_prob);
  const profile = assignClusterInBrowser(row);
  const plan = rulesForNewReservation(row, profile.profile, row.risk_level);
  return {
    id: `SIM-${Date.now().toString().slice(-6)}`,
    hotel: row.hotel,
    guest_name: String(row.guest_name || "").trim(),
    guest_email: String(row.guest_email || "").trim(),
    country: "N/D",
    lead_time: row.lead_time,
    arrival: `${row.arrival_date_day_of_month} ${row.arrival_date_month} ${row.arrival_date_year}`,
    arrival_month: row.arrival_date_month,
    week: row.arrival_date_week_number,
    gender: "N/D",
    meal: row.meal,
    market_segment: row.market_segment,
    distribution_channel: row.distribution_channel,
    repeated_guest: 0,
    previous_cancellations: row.previous_cancellations,
    previous_bookings_not_canceled: 0,
    room_type: row.reserved_room_type,
    customer_type: row.customer_type,
    deposit_type: row.deposit_type || "Unknown",
    special_requests: row.total_of_special_requests,
    has_agent: row.has_agent,
    has_company: row.has_company,
    total_nights: row.total_nights,
    total_guests: row.total_guests,
    adr_per_guest: row.adr_per_guest,
    adr: row.adr,
    is_family_booking: row.is_family_booking,
    country_risk: row.country_risk,
    profile: profile.profile,
    cluster: profile.cluster,
    cancel_prob: row.cancel_prob,
    risk_level: row.risk_level,
    priority: plan.priority,
    channels: plan.channels,
    timing: plan.timing,
    actions: plan.actions,
    global_rules: plan.globalRules,
    profile_description: plan.description,
    spend_total: row.spend_total,
    urgency_score: (riskOrder.length - riskOrder.indexOf(row.risk_level)) * 1000 + row.cancel_prob * 100 + row.spend_total / 100,
    causes: [`Prediccion calculada por XGBoost en el navegador`, `Perfil TLP asignado por distancia a centroides: ${profile.profile}`],
    status: "Pendiente",
    engine_trace: "Reserva nueva evaluada en el dashboard con XGBoost exportado, centroides TLP y reglas derivadas del clustering.",
  };
}

function submitNewReservation(event) {
  event.preventDefault();
  const item = buildNewReservation(event.currentTarget);
  reservations.unshift(item);
  state.selectedMonth = item.arrival_month;
  state.selectedDay = Number(String(item.arrival || "").match(/\d+/)?.[0] || 1);
  summarize();
  renderCalendar();
  renderRiskChart();
  renderProfileBars();
  renderRows();
  byId("newBookingResult").innerHTML = `<strong>${item.id}</strong>: ${item.risk_level} con ${pct.format(item.cancel_prob)}. Perfil ${cleanText(item.profile)}. Acciones propuestas: ${item.actions.length}.`;
  showToast(`Nueva reserva ${item.id} evaluada por el motor IDSS.`);
  closeNewReservationDrawer();
  openDetail(item.id);
}

function openNewReservationDrawer() {
  const drawer = byId("newReservationDrawer");
  const button = byId("newReservationToggle");
  closeDetail();
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  button.setAttribute("aria-expanded", "true");
}

function closeNewReservationDrawer() {
  const drawer = byId("newReservationDrawer");
  const button = byId("newReservationToggle");
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  button.setAttribute("aria-expanded", "false");
}

function bindEvents() {
  if (byId("newReservationToggle")) {
    byId("newReservationToggle").addEventListener("click", openNewReservationDrawer);
  }
  if (byId("newBookingForm")) {
    byId("newBookingForm").addEventListener("submit", submitNewReservation);
  }
  if (byId("calendarMonth")) {
    byId("calendarMonth").addEventListener("change", (event) => {
      state.selectedMonth = event.target.value;
      state.selectedDay = null;
      renderCalendar();
    });
  }
  byId("searchInput").addEventListener("input", (event) => {
    state.query = event.target.value;
    renderRows();
  });

  document.querySelectorAll(".segmented button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".segmented button").forEach((candidate) => candidate.classList.remove("active"));
      button.classList.add("active");
      state.filter = button.dataset.filter;
      renderRows();
    });
  });

  byId("closeDrawer").addEventListener("click", closeDetail);
  byId("detailDrawer").addEventListener("click", (event) => {
    if (event.target.id === "detailDrawer") closeDetail();
  });
  byId("closeNewReservationDrawer").addEventListener("click", closeNewReservationDrawer);
  byId("newReservationDrawer").addEventListener("click", (event) => {
    if (event.target.id === "newReservationDrawer") closeNewReservationDrawer();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (byId("newReservationDrawer").classList.contains("open")) closeNewReservationDrawer();
    if (byId("detailDrawer").classList.contains("open")) closeDetail();
  });
}

function closeDetail() {
  const drawer = byId("detailDrawer");
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

function readStoredWebReservations() {
  try {
    const parsed = JSON.parse(localStorage.getItem("idss_web_reservations") || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    console.warn("No se pudieron cargar reservas web desde localStorage.");
    return [];
  }
}

function readTransferredWebReservations() {
  try {
    const payload = JSON.parse(window.name || "{}");
    if (payload.type !== "idss_web_reservations_transfer" || !Array.isArray(payload.reservations)) return [];
    const stored = readStoredWebReservations();
    const merged = [...payload.reservations, ...stored].filter((item, index, items) => item?.id && items.findIndex((candidate) => candidate.id === item.id) === index);
    try {
      localStorage.setItem("idss_web_reservations", JSON.stringify(merged));
    } catch {
      console.warn("No se pudieron persistir reservas web transferidas.");
    }
    window.name = "";
    return merged;
  } catch {
    return [];
  }
}

function mergeWebReservations() {
  const webReservations = [...readTransferredWebReservations(), ...readStoredWebReservations()].filter(
    (item, index, items) => item?.id && items.findIndex((candidate) => candidate.id === item.id) === index,
  );
  let changed = false;
  for (let index = webReservations.length - 1; index >= 0; index -= 1) {
    const item = webReservations[index];
    if (!reservations.some((reservation) => reservation.id === item.id)) {
      reservations.unshift(item);
      changed = true;
    }
  }
  return changed;
}

function refreshAfterWebReservations() {
  if (!mergeWebReservations()) return;
  summarize();
  renderCalendar();
  renderRiskChart();
  renderProfileBars();
  renderRows();
}

function init() {
  mergeWebReservations();
  window.addEventListener("storage", (event) => {
    if (event.key === "idss_web_reservations") refreshAfterWebReservations();
  });
  window.addEventListener("focus", refreshAfterWebReservations);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshAfterWebReservations();
  });
  state.selectedMonth = busiestMonth();
  summarize();
  renderCalendar();
  renderRiskChart();
  renderProfileBars();
  renderRows();
  bindEvents();
}

init();

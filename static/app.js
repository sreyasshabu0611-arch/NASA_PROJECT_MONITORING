
let astronauts = [];
let heartChart;
let spoChart;

const latest = {};

// Connect to Python API
async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options
    });

    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Request failed");
    }

    return response;
}

// Display current time
function updateClock() {
    document.getElementById("clock").textContent =
        new Date().toLocaleTimeString();
}

setInterval(updateClock, 1000);
updateClock();

// Determine astronaut status
function statusFor(r) {
    if (!r || r.heart_rate === undefined) return "WAITING";

    if (
        r.spo2 < 90 ||
        r.heart_rate > 130 ||
        r.temperature >= 39
    ) {
        return "CRITICAL";
    }

    if (
        r.spo2 < 95 ||
        r.heart_rate > 100 ||
        r.heart_rate < 50 ||
        r.temperature > 38
    ) {
        return "WARNING";
    }

    return "NORMAL";
}

function pillClass(status) {
    if (status === "CRITICAL") return "critical";
    if (status === "WARNING") return "warning";
    return "";
}

// Prevent HTML injection in displayed text
function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    }[c]));
}

// Display astronaut cards
function renderCrew() {
    const grid = document.getElementById("crewGrid");
    grid.innerHTML = "";

    astronauts.forEach(a => {
        const r = latest[a.id] || {};
        const status = statusFor(r);

        const card = document.createElement("article");
        card.className = "crew-card";

        card.innerHTML = `
            <div class="crew-top">
                <div style="display:flex;gap:11px">
                    <div class="avatar">
                        ${escapeHtml(
                            a.name.split(" ")
                            .map(x => x[0]).slice(0, 2).join("")
                        )}
                    </div>

                    <div>
                        <p class="crew-name">${escapeHtml(a.name)}</p>
                        <div class="crew-meta">
                            ${escapeHtml(a.id)} · ${escapeHtml(a.mission)}
                        </div>
                    </div>
                </div>

                <span class="pill ${pillClass(status)}">
                    ${status}
                </span>
            </div>

            <div class="vitals">
                <div class="vital">
                    <span>HEART RATE</span>
                    <b>${r.heart_rate ?? "--"} BPM</b>
                </div>

                <div class="vital">
                    <span>SpO2</span>
                    <b>${r.spo2 ?? "--"}%</b>
                </div>

                <div class="vital">
                    <span>TEMPERATURE</span>
                    <b>${r.temperature ?? "--"} °C</b>
                </div>
            </div>

            <div class="crew-foot">
                <span>${escapeHtml(a.spacecraft || "Unassigned")}</span>
                <span>
                    ${r.timestamp
                        ? new Date(r.timestamp).toLocaleTimeString()
                        : "Waiting for data"}
                </span>
            </div>
        `;

        grid.appendChild(card);
    });

    document.getElementById("totalCrew").textContent =
        astronauts.length;

    document.getElementById("liveStreams").textContent =
        astronauts.filter(a => latest[a.id]).length;
}

// Fill astronaut selection boxes
function fillSelects() {
    const ids = [
        "chartAstronaut",
        "scenarioAstronaut",
        "exportAstronaut"
    ];

    ids.forEach(id => {
        const element = document.getElementById(id);
        const oldValue = element.value;

        element.innerHTML = astronauts.map(a => `
            <option value="${escapeHtml(a.id)}">
                ${escapeHtml(a.name)} (${escapeHtml(a.id)})
            </option>
        `).join("");

        if (astronauts.some(a => a.id === oldValue)) {
            element.value = oldValue;
        }
    });
}

// Load astronaut information
async function loadCrew() {
    astronauts = await (
        await api("/api/astronauts")
    ).json();

    fillSelects();

    for (const a of astronauts) {
        const rows = await (
            await api(`/api/history/${a.id}?limit=1`)
        ).json();

        if (rows.length) {
            latest[a.id] = rows[rows.length - 1];
        }
    }

    renderCrew();
    await refreshAlerts();
    await loadChart();
}

// Load emergency alerts
async function refreshAlerts() {
    const alerts = await (
        await api("/api/alerts")
    ).json();

    const open = alerts.filter(a => !a.acknowledged);

    document.getElementById("openAlerts").textContent =
        open.length;

    const list = document.getElementById("alertList");

    if (!alerts.length) {
        list.innerHTML =
            '<p class="empty">No alerts recorded.</p>';
        return;
    }

    list.innerHTML = alerts.map(a => `
        <div class="alert-row">

            <span class="severity ${a.severity}">
                ${escapeHtml(a.severity)}
            </span>

            <div>
                <b>
                    ${escapeHtml(a.astronaut_name)}
                    · ${escapeHtml(a.parameter)}
                    : ${escapeHtml(a.value)}
                </b>

                <div class="alert-desc">
                    ${escapeHtml(a.description)}
                    · ${new Date(a.timestamp).toLocaleString()}
                </div>
            </div>

            ${
                a.acknowledged
                ? '<span class="subtle">ACKNOWLEDGED</span>'
                : `<button class="button secondary"
                    onclick="acknowledge(${a.id})">
                    Acknowledge
                   </button>`
            }

        </div>
    `).join("");
}

// Acknowledge an alert
async function acknowledge(id) {
    try {
        await api(`/api/alerts/${id}/acknowledge`, {
            method: "POST"
        });

        await refreshAlerts();

    } catch (error) {
        alert(error.message);
    }
}

// Create health charts
function initCharts() {
    const options = {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                ticks: { color: "#7892a9", maxTicksLimit: 6 },
                grid: { color: "#1a3045" }
            },
            y: {
                ticks: { color: "#7892a9" },
                grid: { color: "#1a3045" }
            }
        }
    };

    heartChart = new Chart(
        document.getElementById("heartChart"),
        {
            type: "line",
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    borderColor: "#58d7f5",
                    backgroundColor: "#58d7f522",
                    fill: true,
                    tension: 0.35,
                    pointRadius: 1
                }]
            },
            options
        }
    );

    spoChart = new Chart(
        document.getElementById("spoChart"),
        {
            type: "line",
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    borderColor: "#8b8cff",
                    backgroundColor: "#8b8cff22",
                    fill: true,
                    tension: 0.35,
                    pointRadius: 1
                }]
            },
            options
        }
    );
}

// Load selected astronaut's history
async function loadChart() {
    if (!heartChart) return;

    const id = document.getElementById(
        "chartAstronaut"
    ).value;

    if (!id) return;

    const rows = await (
        await api(`/api/history/${id}?limit=60`)
    ).json();

    updateChartData(rows);
}

// Update graph values
function updateChartData(rows) {
    const labels = rows.map(r =>
        new Date(r.timestamp).toLocaleTimeString()
    );

    heartChart.data.labels = labels;
    heartChart.data.datasets[0].data =
        rows.map(r => r.heart_rate);

    heartChart.update("none");

    spoChart.data.labels = labels;
    spoChart.data.datasets[0].data =
        rows.map(r => r.spo2);

    spoChart.update("none");
}

// WebSocket connection
function connectWebSocket() {
    const scheme =
        location.protocol === "https:" ? "wss" : "ws";

    const socket = new WebSocket(
        `${scheme}://${location.host}/ws`
    );

    socket.onopen = () => {
        document.getElementById("connection").textContent =
            "LIVE CONNECTION";
    };

    socket.onmessage = async event => {
        const message = JSON.parse(event.data);

        if (message.type !== "reading") return;

        const reading = message.reading;

        latest[reading.astronaut_id] = reading;

        renderCrew();

        if (message.alerts && message.alerts.length > 0) {
            await refreshAlerts();
        }

        const selected = document.getElementById(
            "chartAstronaut"
        ).value;

        if (selected === reading.astronaut_id) {
            const rows = await (
                await api(`/api/history/${selected}?limit=60`)
            ).json();

            updateChartData(rows);
        }
    };

    socket.onclose = () => {
        document.getElementById("connection").textContent =
            "RECONNECTING";

        setTimeout(connectWebSocket, 2000);
    };

    socket.onerror = () => socket.close();
}

// Apply a sensor test scenario
async function applyScenario() {
    const id = document.getElementById(
        "scenarioAstronaut"
    ).value;

    const scenario = document.getElementById(
        "scenario"
    ).value;

    try {
        await api(`/api/astronauts/${id}/scenario`, {
            method: "POST",
            body: JSON.stringify({ scenario })
        });

        document.getElementById(
            "scenarioMessage"
        ).textContent =
            `Scenario "${scenario}" applied to ${id}.`;

    } catch (error) {
        document.getElementById(
            "scenarioMessage"
        ).textContent = error.message;
    }
}

// Download CSV report
function exportData() {
    const id = document.getElementById(
        "exportAstronaut"
    ).value;

    if (id) {
        location.href = `/api/export/${id}.csv`;
    }
}

// Open astronaut form
function openAddAstronaut() {
    document.getElementById("formError").textContent = "";
    document.getElementById("addDialog").showModal();
}

// Save new astronaut
document.getElementById("addForm").addEventListener(
    "submit",
    async event => {
        if (event.submitter?.value === "cancel") return;

        event.preventDefault();

        const form = new FormData(event.currentTarget);
        const data = Object.fromEntries(form.entries());

        try {
            await api("/api/astronauts", {
                method: "POST",
                body: JSON.stringify(data)
            });

            document.getElementById("addDialog").close();
            event.currentTarget.reset();

            await loadCrew();

        } catch (error) {
            document.getElementById("formError").textContent =
                error.message;
        }
    }
);

// Start application frontend
async function startApplication() {
    initCharts();

    try {
        await loadCrew();
        connectWebSocket();

    } catch (error) {
        document.getElementById("connection").textContent =
            "SERVER ERROR";

        console.error(error);
    }
}

startApplication();
document.getElementById("logoutButton")
    ?.addEventListener("click", async function() {

        try {

            await fetch("/api/logout", {
                method: "POST"
            });

            window.location.href = "/";

        } catch (error) {

            alert("Unable to logout. Please try again.");

        }

    });
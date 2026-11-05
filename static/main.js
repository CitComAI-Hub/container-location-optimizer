import { api } from "./modules/api.js";
import { LayoutMap } from "./modules/map.js";

const $ = (selector) => document.querySelector(selector);
const fmt = new Intl.NumberFormat("en");
const POLL = 2000;

const ui = {
    loading: $("#loading"),
    loadingMessage: $("#loading-message"),
    dashboard: $("#dashboard"),
    summary: $("#data-summary"),
    layouts: $("#layouts"),
    current: $("#layout-current"),
    currentMetrics: $("#metrics-current"),
    form: $("#new-layout"),
    name: $("#name"),
    containers: $("#containers"),
    serviceLevel: $("#service-level"),
    generations: $("#generations"),
    populationSize: $("#population-size"),
    optimize: $("#optimize"),
    notification: $("#notification"),
    notificationMessage: $("#notification-message"),
};

let map;
let selected = "current";
const cards = new Map(); // job id -> card element
const currentLayouts = new Map(); // service level -> current layout

// ---------------------------------------------------------------- //
function notify(message, kind = "is-danger", autoHide = true) {
    ui.notification.className = `notification ${kind}`;
    ui.notificationMessage.textContent = message;
    if (autoHide) setTimeout(() => ui.notification.classList.add("is-hidden"), 5000);
}
$("#notification-close").addEventListener("click", () => ui.notification.classList.add("is-hidden"));

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metricRows(metrics, baseline) {
    const metres = (v) => `${fmt.format(Math.round(v))} m`;
    // [label, metric, format, compare with the current layout]
    const rows = [
        ["Container sites", "sites", fmt.format, false],
        ["Capacity covers", "capacity_share", (v) => `${(v * 100).toFixed(1)} % of people`, false],
        ["People above capacity", "overload", fmt.format, true],
        ["Mean distance*", "mean_distance", metres, true],
        ["95 % of people within*", "p95_distance", metres, true],
        ["Overloaded containers", "overloaded_sites", fmt.format, false],
    ];
    const fragment = document.createDocumentFragment();
    for (const [label, key, format, compare] of rows) {
        const value = metrics[key];
        const dt = document.createElement("dt");
        dt.textContent = label;
        const dd = document.createElement("dd");
        dd.textContent = format(value);
        if (baseline && compare && baseline[key]) {
            const change = (value - baseline[key]) / baseline[key];
            const delta = document.createElement("span");
            delta.className = "delta";
            const percent = Math.round(change * 1000) / 10; // one decimal, no "-0.0"
            delta.textContent = percent === 0 ? "=" : `${percent > 0 ? "+" : ""}${percent.toFixed(1)} %`;
            dd.appendChild(delta);
        }
        fragment.append(dt, dd);
    }
    return fragment;
}

function select(id, layout) {
    selected = id;
    for (const card of ui.layouts.querySelectorAll(".layout-card")) {
        card.classList.toggle("is-selected", card.dataset.id === id);
    }
    map.showLayout(layout);
}

async function currentLayout(serviceLevel) {
    if (!currentLayouts.has(serviceLevel)) {
        currentLayouts.set(serviceLevel, await api.layout(serviceLevel));
    }
    return currentLayouts.get(serviceLevel);
}

// ---------------------------------------------------------------- //
const STATES = {
    queued: "Waiting in the queue",
    running: "Running",
    done: "Done",
    failed: "Failed",
    cancelled: "Cancelled",
};

function jobCard(job) {
    let card = cards.get(job.id);
    if (!card) {
        card = document.createElement("article");
        card.className = "layout-card";
        card.tabIndex = 0;
        card.dataset.id = job.id;
        card.innerHTML = `<header><span class="layout-name"></span><span class="layout-state"></span></header>
            <progress class="progress is-small is-link" max="1" value="0"></progress>
            <dl class="metrics"></dl>
            <button class="button is-text is-small job-action" type="button"></button>`;
        card.querySelector(".layout-name").textContent = job.name;
        card.querySelector(".job-action").addEventListener("click", async (event) => {
            event.stopPropagation();
            const active = ["queued", "running"].includes(card.dataset.state);
            if (!active && !confirm(`Delete "${job.name}"? It is deleted for every user.`)) return;
            try {
                await api.deleteJob(job.id);
                if (!active) removeCard(job.id);
            } catch (error) {
                notify(error.message);
            }
        });
        const open = () => openJob(job.id);
        card.addEventListener("click", open);
        card.addEventListener("keydown", (event) => event.key === "Enter" && open());
        ui.layouts.appendChild(card);
        cards.set(job.id, card);
    }

    const params = job.params;
    const progress = card.querySelector("progress");
    const generation = job.progress ? job.progress.generation : 0;
    let state = STATES[job.state] || job.state;
    if (job.state === "running") state += ` · ${generation}/${params.generations}`;
    if (job.state === "failed" && job.error) state += `: ${job.error}`;
    card.querySelector(".layout-state").textContent = state;
    card.querySelector(".layout-state").title = state;
    progress.value = job.state === "done" ? 1 : generation / params.generations;
    progress.classList.toggle("is-hidden", !["queued", "running"].includes(job.state));
    const active = ["queued", "running"].includes(job.state);
    card.querySelector(".job-action").textContent = active ? "Cancel" : "Delete";
    card.classList.toggle("is-done", job.state === "done");
    return card;
}

function removeCard(id) {
    const card = cards.get(id);
    if (!card) return;
    card.remove();
    cards.delete(id);
    if (selected === id) showCurrent().catch((e) => notify(e.message));
}

async function openJob(id) {
    const card = cards.get(id);
    if (!card || !card.classList.contains("is-done")) return;
    try {
        const job = await api.job(id);
        const baseline = await currentLayout(job.params.service_level);
        const metrics = card.querySelector(".metrics");
        metrics.replaceChildren(metricRows(job.result.metrics, baseline.metrics));
        select(id, job.result);
    } catch (error) {
        notify(error.message);
    }
}

async function pollJobs() {
    while (true) {
        try {
            const { jobs } = await api.jobs();
            // jobs deleted by someone else, dropped by the server or lost in a restart
            const ids = new Set(jobs.map((job) => job.id));
            for (const id of [...cards.keys()]) if (!ids.has(id)) removeCard(id);
            for (const job of jobs) {
                const card = jobCard(job);
                const wasDone = card.dataset.state === "done";
                card.dataset.state = job.state;
                if (job.state === "done" && !wasDone) {
                    // show the metrics; open it if the user is waiting for it
                    const result = await api.job(job.id);
                    const baseline = await currentLayout(job.params.service_level);
                    card.querySelector(".metrics").replaceChildren(
                        metricRows(result.result.metrics, baseline.metrics));
                    if (card.dataset.waiting) select(job.id, result.result);
                }
            }
        } catch (error) {
            console.error(error);
        }
        await sleep(POLL);
    }
}

// ---------------------------------------------------------------- //
ui.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    ui.optimize.classList.add("is-loading");
    try {
        const job = await api.createJob({
            name: ui.name.value.trim() || `Layout ${cards.size + 1}`,
            containers: Number(ui.containers.value),
            service_level: Number(ui.serviceLevel.value),
            generations: Number(ui.generations.value),
            population_size: Number(ui.populationSize.value),
        });
        jobCard(job).dataset.waiting = "1";
        ui.name.value = "";
        notify("Added to the queue", "is-success");
    } catch (error) {
        notify(error.message);
    } finally {
        ui.optimize.classList.remove("is-loading");
    }
});

async function showCurrent() {
    const serviceLevel = Number(ui.serviceLevel.value) || 1000;
    const layout = await currentLayout(serviceLevel);
    ui.currentMetrics.replaceChildren(metricRows(layout.metrics));
    select("current", layout);
}
ui.current.dataset.id = "current";
ui.current.addEventListener("click", () => showCurrent().catch((e) => notify(e.message)));
ui.serviceLevel.addEventListener("change", () => {
    if (selected === "current") showCurrent().catch((e) => notify(e.message));
});

async function waitForData() {
    while (true) {
        try {
            const status = await api.status();
            if (status.status === "ready") return status;
            ui.loadingMessage.textContent = status.status === "error"
                ? `Could not load the data: ${status.error}. Retrying…`
                : "Loading the containers and the population…";
        } catch (error) {
            ui.loadingMessage.textContent = error.message;
        }
        await sleep(3000);
    }
}

(async function main() {
    const status = await waitForData();
    ui.loading.classList.add("is-hidden");
    ui.dashboard.classList.remove("is-hidden");

    ui.summary.textContent =
        `${fmt.format(status.containers)} containers on ${fmt.format(status.current_sites)} sites · ` +
        `${fmt.format(status.candidate_sites)} candidate sites · ${fmt.format(status.people)} people ` +
        `(${status.population_source}). *Straight-line distance.`;
    ui.containers.value = status.containers;
    ui.containers.max = status.candidate_sites;

    map = new LayoutMap("map");
    map.setRegion(status.region);
    map.setCandidates(status.candidates);
    await showCurrent();
    pollJobs();
})();

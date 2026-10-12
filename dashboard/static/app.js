const METRICS = {
  dialogue_experience: {
    label: "客观对话体验",
    description: "综合评估人格一致性、对话体感和情感支持。分数越高，对话体验越好。",
    lowerIsBetter: false,
  },
  action_ability: {
    label: "行动能力",
    description: "评估模型能否选择正确行动，并完成行动闭环。额外调用工具不会提高分数。",
    lowerIsBetter: false,
  },
  distortion_rate: {
    label: "失真度",
    description: "表示每次回复中的加权失真事件数。数值越低越好。",
    lowerIsBetter: true,
  },
  availability: {
    label: "可用性",
    description: "表示有效生成数与尝试数的比例，仅作为模型可靠性参考。",
    lowerIsBetter: false,
  },
};

const state = {
  reports: [], errors: [], selected: new Set(), metric: "dialogue_experience", capture: false, benchmarkVersion: null,
};

const elements = {
  chart: document.querySelector("#chart"),
  benchmarkTitle: document.querySelector("#benchmark-title"),
  metricTitle: document.querySelector("#metric-title"),
  metricDescription: document.querySelector("#metric-description"),
  metricTabs: document.querySelector("#metric-tabs"),
  reportCount: document.querySelector("#report-count"),
  reportOptions: document.querySelector("#report-options"),
  selectAll: document.querySelector("#select-all"),
  captureButton: document.querySelector("#capture-button"),
  reportPicker: document.querySelector("#report-picker"),
  errorStrip: document.querySelector("#error-strip"),
};

function reportLabel(report) {
  return report.models.join(" · ") || "空报告";
}

function readUrlState() {
  const params = new URLSearchParams(location.search);
  const metric = params.get("metric");
  if (metric && METRICS[metric]) state.metric = metric;
  state.capture = params.get("capture") === "1";
  document.body.classList.toggle("capture", state.capture);
  return params.has("reports") ? new Set(params.get("reports").split(",").filter(Boolean)) : null;
}

function writeUrlState() {
  const params = new URLSearchParams();
  params.set("reports", [...state.selected].join(","));
  params.set("metric", state.metric);
  if (state.capture) params.set("capture", "1");
  history.replaceState(null, "", `${location.pathname}?${params}`);
}

function formatModelName(model) {
  const normalized = model.toLowerCase().replaceAll("-", "_");
  const exactNames = {
    deepseekflash: "DeepSeek Flash 0731",
    deepseek_flash: "DeepSeek Flash 0731",
    qwen3_8: "Qwen 3.8 27B",
  };
  if (exactNames[normalized]) return exactNames[normalized];

  const familyMatch = normalized.match(/^(gpt|qwen|glm)(\d+)(?:_(\d+))?(?:_(.+))?$/);
  if (familyMatch) {
    const [, family, major, minor, suffix] = familyMatch;
    const brands = { gpt: "GPT", qwen: "Qwen", glm: "GLM" };
    const version = minor ? `${major}.${minor}` : major;
    const suffixName = suffix
      ? ` ${suffix.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ")}`
      : "";
    return `${brands[family]} ${version}${suffixName}`;
  }

  return model.split(/[_-]+/).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function niceDistortionMax(values) {
  const highest = Math.max(...values, 0);
  if (highest <= 0) return 0.1;
  const target = highest * 1.1;
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const normalized = target / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return Math.max(0.1, step * magnitude);
}

function niceAxisStep(range) {
  const roughStep = range / 4;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const normalized = roughStep / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

function metricDomain(values, lowerIsBetter) {
  if (!values.length) return { min: 0, max: 1 };
  if (lowerIsBetter) return { min: 0, max: niceDistortionMax(values) };

  const lowest = Math.min(...values);
  const highest = Math.max(...values);
  const padding = Math.max((highest - lowest) * 0.3, 0.015);
  const roughMin = Math.max(0, lowest - padding);
  const roughMax = Math.min(1, highest + padding);
  const step = niceAxisStep(Math.max(roughMax - roughMin, 0.02));
  let min = Math.max(0, Math.floor(roughMin / step) * step);
  let max = Math.min(1, Math.ceil(roughMax / step) * step);
  if (max <= min) {
    min = Math.max(0, lowest - 0.05);
    max = Math.min(1, highest + 0.05);
  }
  return { min, max };
}

function selectedRows() {
  const latestByModel = new Map();
  state.reports.forEach((report) => {
    if (!state.selected.has(report.filename)) return;
    report.models.forEach((model) => {
      const current = latestByModel.get(model);
      if (current && current.report.generated_at >= report.generated_at) return;
      latestByModel.set(model, {
        model,
        report,
        value: report.summary[state.metric][model],
      });
    });
  });
  const rows = [...latestByModel.values()];
  const lowerIsBetter = METRICS[state.metric].lowerIsBetter;
  return rows.sort((a, b) => {
    if (a.value === null) return 1;
    if (b.value === null) return -1;
    return lowerIsBetter ? a.value - b.value : b.value - a.value;
  });
}

function fitModelLabels() {
  document.querySelectorAll(".model-name").forEach((label) => {
    label.style.removeProperty("font-size");
    let fittedSize = Number.parseFloat(getComputedStyle(label).fontSize);
    while (label.scrollWidth > label.clientWidth && fittedSize > 14) {
      fittedSize -= 1;
      label.style.fontSize = `${fittedSize}px`;
    }
  });
}

function renderTabs() {
  elements.metricTabs.replaceChildren(...Object.entries(METRICS).map(([key, metric]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "metric-tab";
    button.role = "tab";
    button.dataset.metric = key;
    button.setAttribute("aria-selected", String(state.metric === key));
    button.textContent = metric.label;
    button.addEventListener("click", () => {
      state.metric = key;
      writeUrlState();
      render();
    });
    return button;
  }));
}

function renderReportOptions() {
  elements.reportOptions.replaceChildren(...state.reports.map((report) => {
    const label = document.createElement("label");
    label.className = "report-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = state.selected.has(report.filename);
    input.addEventListener("change", () => {
      if (input.checked) state.selected.add(report.filename);
      else state.selected.delete(report.filename);
      writeUrlState();
      render();
    });
    const text = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = reportLabel(report);
    const details = document.createElement("small");
    details.textContent = `Benchmark ${report.config.benchmark_version || "未知版本"} · ${report.config.harness || "未知管线"}`;
    text.append(name, details);
    label.append(input, text);
    return label;
  }));

  const count = state.selected.size;
  elements.reportCount.textContent = count ? `已选 ${count} 个报告` : "选择报告";
  elements.selectAll.checked = count > 0 && count === state.reports.length;
  elements.selectAll.indeterminate = count > 0 && count < state.reports.length;
}

function renderErrors() {
  if (!state.errors.length) {
    elements.errorStrip.hidden = true;
    elements.errorStrip.textContent = "";
    return;
  }
  elements.errorStrip.hidden = false;
  elements.errorStrip.textContent = state.errors.map((error) => `${error.filename}：${error.message}`).join("；");
}

function renderChart() {
  const metric = METRICS[state.metric];
  elements.metricTitle.textContent = metric.label;
  elements.metricDescription.textContent = metric.description;
  elements.benchmarkTitle.textContent = state.benchmarkVersion
    ? `MAS-PERSONALITY-BENCHMARK · Ver ${state.benchmarkVersion}`
    : "MAS-PERSONALITY-BENCHMARK";

  const rows = selectedRows();
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = state.reports.length ? "请选择至少一个报告" : "没有可用的 Benchmark 报告";
    elements.chart.replaceChildren(empty);
    return;
  }

  const numericValues = rows.filter((row) => row.value !== null).map((row) => row.value);
  const domain = metricDomain(numericValues, metric.lowerIsBetter);
  const domainRange = domain.max - domain.min;
  const best = numericValues.length ? (metric.lowerIsBetter ? Math.min(...numericValues) : Math.max(...numericValues)) : null;
  const bars = document.createElement("div");
  bars.className = "bars";
  bars.style.setProperty("--row-count", rows.length);
  bars.replaceChildren(...rows.map((row) => {
    const barRow = document.createElement("div");
    barRow.className = "bar-row";
    if (row.value !== null && row.value === best) barRow.classList.add("best");
    const label = document.createElement("div");
    label.className = "model-label";
    const model = document.createElement("div");
    model.className = "model-name";
    model.textContent = formatModelName(row.model);
    model.title = model.textContent;
    label.append(model);

    const track = document.createElement("div");
    track.className = "bar-track";
    track.setAttribute("aria-label", row.value === null ? `${row.model} 无数据` : `${row.model} ${row.value.toFixed(4)}`);
    const barRatio = row.value === null ? 0 : Math.max(0, Math.min(1, (row.value - domain.min) / domainRange));
    const barWidth = `${barRatio * 100}%`;
    track.style.setProperty("--bar-width", barWidth);
    if (row.value !== null) {
      const fill = document.createElement("div");
      fill.className = "bar-fill";
      track.append(fill);
    }

    const value = document.createElement("div");
    value.className = `bar-value${row.value === null ? " missing" : ""}`;
    if (row.value !== null && barRatio >= 0.9) value.classList.add("at-end");
    value.textContent = row.value === null ? "N/A" : row.value.toFixed(2);
    value.title = row.value === null ? "无数据" : row.value.toFixed(4);
    track.append(value);
    barRow.append(label, track);
    return barRow;
  }));

  const axis = document.createElement("div");
  axis.className = "axis";
  const spacer = document.createElement("span");
  const ticks = document.createElement("div");
  ticks.className = "axis-ticks";
  const tickDecimals = domainRange <= 0.1 ? 3 : 2;
  for (let index = 0; index <= 4; index += 1) {
    const tick = document.createElement("span");
    tick.textContent = (domain.min + domainRange * index / 4).toFixed(tickDecimals);
    ticks.append(tick);
  }
  axis.append(spacer, ticks);
  elements.chart.replaceChildren(bars, axis);
  fitModelLabels();
}

function render() {
  document.body.classList.toggle("capture", state.capture);
  renderTabs();
  renderReportOptions();
  renderErrors();
  renderChart();
}

elements.selectAll.addEventListener("change", () => {
  state.selected = elements.selectAll.checked ? new Set(state.reports.map((report) => report.filename)) : new Set();
  writeUrlState();
  render();
});

elements.captureButton.addEventListener("click", () => {
  state.capture = true;
  elements.reportPicker.open = false;
  writeUrlState();
  render();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.capture) {
    state.capture = false;
    writeUrlState();
    render();
  }
});

let resizeFrame;
window.addEventListener("resize", () => {
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(fitModelLabels);
});

async function initialize() {
  const requestedReports = readUrlState();
  try {
    const response = await fetch("/api/reports", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.reports = payload.reports;
    state.errors = payload.errors;
    state.benchmarkVersion = payload.benchmark_version;
    const available = new Set(state.reports.map((report) => report.filename));
    state.selected = requestedReports === null
      ? new Set(available)
      : new Set([...requestedReports].filter((filename) => available.has(filename)));
  } catch (error) {
    state.errors = [{ filename: "API", message: `报告加载失败：${error.message}` }];
  }
  writeUrlState();
  render();
}

initialize();

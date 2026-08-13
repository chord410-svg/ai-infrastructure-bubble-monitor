const latestUrl = new URL("./data/latest.json", window.location.href);
const historyUrl = new URL("./data/history.json", window.location.href);

const MODULES = [
  { id: "demand", label: "需求", index: "01" },
  { id: "supply", label: "供給", index: "02" },
  { id: "investment", label: "投資與現金流", index: "03" },
  { id: "market", label: "市場與融資壓力", index: "04" },
];

const STATE_COPY = {
  INSUFFICIENT_EVIDENCE: ["證據不足，暫不判讀", "正式資料、歷史長度或新鮮度尚未通過門檻。"],
  FUNDED_EXPANSION: ["擴張仍由現金流支撐", "結構壓力與金融觸發均處於較低歷史位置。"],
  MIXED_EVIDENCE: ["證據分歧，維持觀察", "目前沒有形成一致的泡沫累積或破裂訊號。"],
  WATCH_NOT_BREAKING: ["結構壓力偏高，尚無破裂證據", "投資壓力累積，但金融條件尚未共同惡化。"],
  PRE_BREAK_FINANCIAL: ["結構與金融壓力開始共振", "需連續兩期確認，避免把單週波動誤判為破裂。"],
  FINANCIAL_UNWIND: ["金融面出現明確鬆動風險", "結構壓力與破裂觸發都位於高歷史區間。"],
  CYCLICAL_STRESS: ["金融環境緊縮，但未見高結構壓力", "較像廣泛景氣壓力，不足以單獨指向 AI 泡沫。"],
};

async function loadJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url.pathname}: ${response.status}`);
  return response.json();
}

function isStale(lastSuccessfulUpdate, now = new Date()) {
  if (!lastSuccessfulUpdate) return true;
  return (now - new Date(lastSuccessfulUpdate)) / 86400000 > 14;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function formatScore(value) {
  return value === null || value === undefined ? "—" : String(Math.round(value));
}

function formatRaw(item) {
  if (item.raw_value === null || item.raw_value === undefined) return "—";
  if (item.unit === "index") return Number(item.raw_value).toFixed(3);
  if (item.unit === "ratio") return `${Number(item.raw_value).toFixed(2)}×`;
  return `${(Number(item.raw_value) * 100).toFixed(1)}%`;
}

function formatInput(value, unit) {
  if (value === null || value === undefined) return "—";
  const number = Number(value);
  if (unit === "USD") return `${number < 0 ? "−" : ""}US$${Math.abs(number / 1e9).toFixed(1)}B`;
  if (unit === "decimal") return `${(number * 100).toFixed(1)}%`;
  if (unit === "points") return `${number >= 0 ? "+" : ""}${number.toFixed(1)} 點`;
  if (unit === "index") return number.toFixed(3);
  return number.toLocaleString("zh-TW");
}

function safeExternalLink(link) {
  const anchor = el("a", "", `${link.label} ↗`);
  anchor.href = link.url;
  anchor.target = "_blank";
  anchor.rel = "noreferrer";
  return anchor;
}

function githubRepositoryUrl(relativePath = "") {
  const host = window.location.hostname;
  if (!host.endsWith(".github.io")) return null;
  const owner = host.slice(0, -".github.io".length);
  const repository = window.location.pathname.split("/").filter(Boolean)[0];
  if (!owner || !repository) return null;
  return `https://github.com/${owner}/${repository}/${relativePath}`.replace(/\/$/, "");
}

function renderSummary(packet) {
  const staleNow = isStale(packet.last_successful_update);
  const copy = STATE_COPY[packet.state] || STATE_COPY.INSUFFICIENT_EVIDENCE;
  document.querySelector("#state-title").textContent = staleNow ? "資料過期，暫停判讀" : copy[0];
  const persistencePending = (packet.reason_codes || []).includes("PERSISTENCE_PENDING");
  document.querySelector("#state-description").textContent = staleNow
    ? "超過 14 天沒有成功驗證全部來源；舊觀測不再顯示為當前分數。"
    : packet.state === "PRE_BREAK_FINANCIAL" && !persistencePending
    ? "結構壓力與金融觸發已連續兩期同時偏高，仍須搭配尚未涵蓋的需求與供給證據解讀。"
    : copy[1];
  document.querySelector("#structural-score").textContent = staleNow ? "—" : formatScore(packet.structural_pressure);
  document.querySelector("#trigger-score").textContent = staleNow ? "—" : formatScore(packet.financial_break_trigger);
  document.querySelector("#confidence").textContent = staleNow ? "已啟用指標資料信心 —" : `已啟用指標資料信心 ${Math.round((packet.confidence || 0) * 100)}%`;
  const breakdown = packet.confidence_breakdown || {};
  document.querySelector("#confidence-detail").textContent = `公司覆蓋 ${Math.round((breakdown.coverage || 0) * 100)}% · 財報新鮮度 ${Math.round((breakdown.company_freshness || 0) * 100)}% · NFCI 新鮮度 ${Math.round((breakdown.nfci_freshness || 0) * 100)}%`;
  document.querySelector("#coverage-count").textContent = `${packet.coverage.enabled} / ${packet.coverage.planned}`;
  document.querySelector("#coverage-ring-value").textContent = packet.coverage.enabled;
  document.querySelector(".coverage-ring").style.setProperty("--progress", `${packet.coverage.enabled / packet.coverage.planned * 360}deg`);
  document.querySelector("#model-version").textContent = `${packet.model.version} · 生效 ${packet.model.effective_date}`;
  document.querySelector("#last-updated").textContent = `最後成功更新：${packet.last_successful_update ? new Date(packet.last_successful_update).toLocaleString("zh-TW") : "尚無"}`;

  const banner = document.querySelector("#status-banner");
  if (packet.as_of && !staleNow) banner.classList.add("is-live");
  if (staleNow) banner.classList.add("is-stale");
  const stale = document.querySelector("#stale-warning");
  if (staleNow) {
    stale.hidden = false;
    stale.textContent = packet.last_successful_update ? "資料已超過 14 天未成功更新，請先檢查來源狀態。" : "尚未有成功更新紀錄。";
  } else {
    stale.hidden = true;
  }
}

function renderJudgement(packet) {
  const labels = {
    SCORES_UNAVAILABLE: "資料或歷史尚未通過計分門檻",
    STRUCTURAL_PRESSURE_ELEVATED: "結構壓力位於較高歷史區間",
    FINANCIAL_TRIGGER_ELEVATED: "金融破裂觸發位於較高歷史區間",
    PERSISTENCE_PENDING: "狀態仍等待連續兩期確認",
    PARTIAL_COMPANY_COVERAGE: "公司籃子資料尚未完整",
    STRUCTURAL_PRESSURE_NOT_ELEVATED: "結構壓力尚未進入高歷史區間",
    FINANCIAL_BREAK_NOT_CONFIRMED: "金融破裂觸發尚未確認",
  };
  const fill = (selector, codes, empty) => {
    const list = document.querySelector(selector);
    const values = codes.length ? codes.map(code => labels[code] || code) : [empty];
    list.replaceChildren(...values.map(value => el("li", "", value)));
  };
  if (isStale(packet.last_successful_update)) {
    fill("#reason-list", [], "過期觀測已排除目前判讀");
    fill("#counter-list", [], "等待全部來源重新驗證");
    return;
  }
  fill("#reason-list", packet.reason_codes || [], "目前沒有額外的支持訊號");
  fill("#counter-list", packet.counter_evidence || [], "目前沒有足以降低警戒的反證");
}

function roleTrace(role) {
  const block = el("div", "role-trace");
  block.append(el("span", `role-chip ${role.score}`, role.score === "structural" ? "結構壓力" : "破裂觸發"));
  block.append(el("p", "role-formula", role.formula));
  const math = el("p", "role-math");
  const risk = role.risk_percentile == null ? "—" : `${role.risk_percentile.toFixed(1)} 百分位`;
  const weight = `${Math.round(role.weight * 100)}%`;
  const contribution = role.contribution == null ? "—" : `${role.contribution.toFixed(2)} 分`;
  math.textContent = `${risk} × ${weight} = ${contribution}`;
  block.append(math);
  return block;
}

function indicatorTable(items) {
  const wrap = el("div", "details-body");
  const table = el("table", "indicator-table");
  const head = el("thead");
  const headerRow = el("tr");
  ["指標與原始數值", "代入公式 → 歷史百分位 → 分數貢獻", "資料日期與涵蓋", "官方來源"].forEach(label => headerRow.append(el("th", "", label)));
  head.append(headerRow);
  table.append(head);
  const body = el("tbody");
  items.forEach(item => {
    const row = el("tr");
    const name = el("td", "", item.label);
    name.append(el("strong", "raw-value", formatRaw(item)));
    name.append(el("small", "", item.status === "not_covered" ? item.missing_reason : item.formula));
    if (item.calculation_inputs?.length) {
      const inputs = el("dl", "calculation-inputs");
      item.calculation_inputs.forEach(input => {
        inputs.append(el("dt", "", input.label), el("dd", "", formatInput(input.value, input.unit)));
      });
      name.append(inputs);
    }
    row.append(name);
    const traceCell = el("td");
    const roles = item.model_roles || [];
    if (roles.length) roles.forEach(role => traceCell.append(roleTrace(role)));
    else traceCell.append(el("span", "not-scored", item.status === "not_covered" ? "尚未納入模型" : "等待足夠歷史"));
    row.append(traceCell);
    const dateCell = el("td", "", item.data_period || "—");
    dateCell.append(el("small", "", item.published_at ? `公布 ${item.published_at}` : "尚無正式資料"));
    if (item.company_coverage?.length) {
      const coverage = el("div", "company-coverage");
      item.company_coverage.forEach(company => coverage.append(el("span", "", `${company.symbol} ${company.period_end}`)));
      dateCell.append(coverage);
    }
    row.append(dateCell);
    const linksCell = el("td");
    const links = el("div", "indicator-links");
    item.source_links.forEach(link => links.append(safeExternalLink(link)));
    const method = el("a", "", "查看計算方法 ↗");
    method.href = githubRepositoryUrl("tree/main/src") || "#method";
    links.append(method);
    const history = githubRepositoryUrl(`tree/main/data/observations/by-indicator/${item.id}`);
    if (history && item.status === "available") {
      const historyLink = el("a", "", "純數值歷史 ↗");
      historyLink.href = history;
      historyLink.target = "_blank";
      historyLink.rel = "noreferrer";
      links.append(historyLink);
    }
    linksCell.append(links);
    row.append(linksCell);
    body.append(row);
  });
  table.append(body);
  wrap.append(table);
  return wrap;
}

function moduleEmptyState(items, hasAvailableItems = false) {
  const wrap = el("div", "details-body module-empty");
  wrap.append(el(
    "p",
    "module-empty-intro",
    hasAvailableItems
      ? "以下規劃指標尚未接入，因此不參與目前分數："
      : "本模組尚未接入正式數值，因此不參與目前分數：",
  ));
  const list = el("ul", "planned-list");
  items.forEach(item => {
    const row = el("li");
    row.append(
      el("strong", "", item.label),
      el("span", "", item.missing_reason || "尚未接入公開且可持續維護的數值來源"),
    );
    list.append(row);
  });
  wrap.append(list);
  return wrap;
}

function renderRailStatus(moduleId, available, planned) {
  const status = document.querySelector(`#rail-${moduleId}-status`);
  if (!status) return;
  status.textContent = available ? `已接入 ${available}/${planned}` : "尚未涵蓋";
  status.classList.toggle("active", available > 0);
}

function renderIndicators(indicators) {
  const container = document.querySelector("#indicator-list");
  container.replaceChildren();
  MODULES.forEach(module => {
    const items = indicators.filter(item => item.module === module.id);
    const details = el("details");
    if (module.id === "investment") details.open = true;
    const summary = el("summary");
    summary.append(el("span", "", module.index), el("strong", "", module.label));
    const availableItems = items.filter(item => item.status === "available");
    const plannedItems = items.filter(item => item.status === "not_covered");
    renderRailStatus(module.id, availableItems.length, items.length);
    summary.append(el("em", "", availableItems.length ? `可取得 ${availableItems.length}/${items.length}` : "尚未涵蓋"));
    details.append(summary);
    if (availableItems.length) details.append(indicatorTable(availableItems));
    if (plannedItems.length) details.append(moduleEmptyState(plannedItems, Boolean(availableItems.length)));
    container.append(details);
  });
}

function renderSources(links) {
  if (!links.length) return;
  const list = document.querySelector("#source-list");
  list.replaceChildren();
  links.forEach(link => {
    const item = el("li");
    item.append(safeExternalLink(link));
    list.append(item);
  });
}

function drawTrend(history) {
  const valid = history.filter(item => item.structural_pressure != null && item.financial_break_trigger != null).slice(-12);
  const canvas = document.querySelector("#trend-chart");
  const fallback = document.querySelector("#trend-fallback");
  const status = document.querySelector("#trend-status");
  if (!valid.length) {
    canvas.style.display = "none";
    status.textContent = "尚無可計分的歷史快照。";
    fallback.textContent = "歷史資料尚未建立。";
    return;
  }
  status.textContent = valid.length === 1
    ? "目前累積 1 / 12 週；至少 2 筆後才會形成折線。"
    : `目前顯示最近 ${valid.length} / 12 週。`;
  canvas.style.display = "block";
  fallback.replaceChildren();
  const table = el("table", "sr-only");
  valid.forEach(item => {
    const row = el("tr");
    row.append(el("td", "", item.date), el("td", "", item.structural_pressure), el("td", "", item.financial_break_trigger));
    table.append(row);
  });
  fallback.append(table);
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = "#cfd6dd";
  context.lineWidth = 1;
  [0,25,50,75,100].forEach(value => {
    const y = 230 - value * 2;
    context.beginPath(); context.moveTo(42,y); context.lineTo(880,y); context.stroke();
    context.fillStyle = "#607086"; context.font = "12px sans-serif"; context.fillText(String(value),8,y+4);
  });
  [["structural_pressure","#b66a00"],["financial_break_trigger","#0b7998"]].forEach(([key,color]) => {
    context.strokeStyle = color; context.lineWidth = 3; context.beginPath();
    valid.forEach((item,index) => {
      const x = valid.length === 1 ? 461 : 42 + index * (838 / (valid.length - 1));
      const y = 230 - item[key] * 2;
      index ? context.lineTo(x,y) : context.moveTo(x,y);
    });
    context.stroke();
    context.fillStyle = color;
    valid.forEach((item,index) => {
      const x = valid.length === 1 ? 461 : 42 + index * (838 / (valid.length - 1));
      const y = 230 - item[key] * 2;
      context.beginPath(); context.arc(x,y,4,0,Math.PI*2); context.fill();
    });
  });
}

function renderMissing(codes, indicators) {
  const labels = {
    TOKEN_DEMAND_UNAVAILABLE: "Token 需求", EFFECTIVE_COMPUTE_UNAVAILABLE: "有效算力",
    GPU_AVAILABILITY_UNAVAILABLE: "GPU 可用容量", GPU_RENTAL_PRICE_UNAVAILABLE: "GPU 租金",
    DATACENTER_POWER_UNAVAILABLE: "資料中心與電力", AI_VALUATION_UNAVAILABLE: "AI 估值",
    AI_FUNDING_COST_UNAVAILABLE: "AI 融資成本",
  };
  const list = document.querySelector("#missing-list");
  const catalogGaps = indicators.filter(item => item.status === "not_covered").map(item => item.label);
  const values = catalogGaps.length ? catalogGaps : codes.map(code => labels[code] || code);
  list.replaceChildren(...[...new Set(values)].map(value => el("span", "", value)));
}

async function start() {
  try {
    const [packet, history] = await Promise.all([loadJson(latestUrl), loadJson(historyUrl)]);
    renderSummary(packet);
    renderJudgement(packet);
    renderIndicators(packet.indicators || []);
    renderSources(packet.source_links || []);
    renderMissing(packet.missing_evidence || [], packet.indicators || []);
    drawTrend(history);
    const repositoryMethod = githubRepositoryUrl("tree/main/src");
    if (repositoryMethod) {
      const methodLink = document.querySelector("#method-link");
      methodLink.href = repositoryMethod;
      methodLink.textContent = "查看 GitHub 計算方法 ↗";
      methodLink.target = "_blank";
      methodLink.rel = "noreferrer";
    }
  } catch (error) {
    document.querySelector("#state-title").textContent = "資料載入失敗";
    document.querySelector("#state-description").textContent = "目前保留方法與官方來源；量化結果暫不顯示。";
    document.querySelector("#stale-warning").hidden = false;
    document.querySelector("#stale-warning").textContent = `資料載入失敗：${error.message}`;
  }
}

start();

import {validateReport, filterTrials, compareShapes, formatNumber as num} from './report.js';
import * as sample from './sample.js';

const $ = id => document.getElementById(id);
const state = {view: 'benchmark', benchmark: null, crash: null, limit: 100, busy: false};
const titles = {benchmark: ['Chọn kiến trúc cho doanh nghiệp', 'Đối chiếu chất lượng, độ ổn định và chi phí trên cùng bộ thử nghiệm.'], crash: ['Crash safety', 'Theo dõi tính an toàn khi gián đoạn và chạy lại.']};
const names = {workflow: 'Workflow', single: 'Single agent', orchestrator: 'Orchestrator', swarm: 'Swarm'};
const percent = value => typeof value === 'number' && Number.isFinite(value) ? `${num(value * 100, 1)}%` : '—';
function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function badge(value) {
  return element('span', value === true ? 'Đạt' : value === false ? 'Không đạt' : 'Chưa chấm', `badge ${value === true ? 'passed' : value === false ? 'failed' : 'ungraded'}`);
}
function row(values) {
  const tr = element('tr');
  for (const value of values) {
    const td = element('td');
    if (value instanceof Node) td.append(value); else td.textContent = value ?? '—';
    tr.append(td);
  }
  return tr;
}
function empty(tbody, columns, message) {
  const td = element('td', message); td.colSpan = columns;
  const tr = element('tr'); tr.append(td); tbody.append(tr);
}
function renderSource() {
  const entry = state[state.view];
  $('source-label').textContent = entry.sample ? 'Dữ liệu mẫu · Không dùng làm bằng chứng nộp bài' : 'Đang xem báo cáo thật';
  $('source-detail').textContent = entry.source;
  document.querySelector('.source-panel').classList.toggle('sample', entry.sample);
  const variables = state.benchmark.data.controlled_variables;
  $('metadata').textContent = state.view === 'benchmark'
    ? `Backend: ${variables?.model_backend ?? '—'} · Seed: ${variables?.seeds?.join(', ') ?? '—'}`
    : 'Kiểm tra ledger và audit sau resume';
}
function renderBenchmark() {
  const {by_shape, trials} = state.benchmark.data;
  populateSelect('baseline', Object.keys(by_shape), 'single');
  populateSelect('claim-select', [...new Set(trials.map(trial => trial.claim_id))].sort());
  renderDecision();
  renderScenario();
  $('shape-cards').replaceChildren(); $('comparison').replaceChildren();
  const selected = $('shape-filter').value;
  $('shape-filter').replaceChildren(new Option('Tất cả', 'all'));
  for (const [shape, stats] of Object.entries(by_shape)) {
    $('shape-filter').add(new Option(names[shape] ?? shape, shape));
    const card = element('article', undefined, 'shape-card');
    card.append(element('h3', names[shape] ?? shape), element('strong', percent(stats.pass_rate), 'rate'), element('p', 'Tỷ lệ đạt'));
    card.append(element('p', `${num(stats.cost_per_success_vnd)} VND / thành công`, 'card-cost'));
    const track = element('div', undefined, 'bar-track');
    const fill = element('div', undefined, 'bar-fill');
    fill.style.width = `${typeof stats.pass_rate === 'number' ? Math.max(0, Math.min(100, stats.pass_rate * 100)) : 0}%`;
    track.append(fill); card.append(track, element('p', `${num(stats.graded_trials, 0)} / ${num(stats.trials, 0)} lượt đã chấm`));
    $('shape-cards').append(card);
    $('comparison').append(row([names[shape] ?? shape, percent(stats.pass_rate), percent(stats.pass_5), num(stats.seed_variance, 6), num(stats.cost_per_success_vnd), num(stats.mean_steps), num(stats.mean_model_calls), num(stats.mean_tool_calls)]));
  }
  if (!Object.keys(by_shape).length) empty($('comparison'), 8, 'Báo cáo chưa có chỉ số theo shape.');
  if (Object.hasOwn(by_shape, selected)) $('shape-filter').value = selected;
  // A shape may have trials but no summary yet.
  for (const shape of new Set(trials.map(item => item.shape))) {
    if (!Object.hasOwn(by_shape, shape)) $('shape-filter').add(new Option(names[shape] ?? shape, shape));
  }
  renderTrials();
}

function populateSelect(id, values, fallback) {
  const previous = $(id).value;
  $(id).replaceChildren(...values.map(value => new Option(id === 'baseline' ? names[value] ?? value : String(value), String(value))));
  if (values.map(String).includes(previous)) $(id).value = previous;
  else if (fallback && values.includes(fallback)) $(id).value = fallback;
}

function chartBar(value, max, label, className) {
  const group = element('div', undefined, 'chart-bar-group');
  const track = element('div', undefined, 'comparison-track');
  const bar = element('div', undefined, `comparison-fill ${className}`);
  const finite = typeof value === 'number' && Number.isFinite(value);
  bar.style.width = `${finite && max > 0 ? Math.max(0, Math.min(100, value / max * 100)) : 0}%`;
  track.append(bar); group.append(track, element('span', label, 'chart-value'));
  return group;
}

function renderDecision() {
  const entry = state.benchmark;
  const report = entry.data;
  const threshold = Number($('quality-threshold').value);
  const baseline = $('baseline').value;
  const decision = compareShapes(report, threshold, baseline);
  const winnerNames = decision.winners.map(shape => names[shape] ?? shape).join(' / ');
  $('decision-tag').textContent = entry.sample ? 'Minh họa bằng dữ liệu mẫu' : 'Đề xuất từ benchmark public';
  $('decision-title').textContent = decision.winners.length
    ? `${decision.winners.length === 1 ? 'Ưu tiên' : 'Đồng hạng chi phí'} ${winnerNames}`
    : 'Chưa đủ cơ sở chọn shape';
  $('decision-reason').textContent = decision.winners.length
    ? `Chi phí / thành công thấp nhất (${num(decision.cost)} VND) trong các shape được chấm đầy đủ và đạt pass rate ≥ ${percent(threshold)} trên cùng bộ claim × seed.`
    : !decision.comparable ? 'Cần ít nhất hai shape chạy trên cùng bộ claim × seed, không có lượt trùng.' : 'Chưa có shape đủ số liệu chi phí, được chấm đầy đủ và đạt ngưỡng chất lượng đã chọn.';
  const crash = state.crash;
  const crashText = crash.sample ? 'Crash safety hiện là dữ liệu mẫu.' : `Crash suite chung: ${crash.data.passed}/${crash.data.count}; không phải phép đo an toàn riêng từng shape.`;
  $('decision-scope').textContent = `${crashText} Đề xuất kinh tế từ MockLLM và chi phí mô phỏng; cần đối chiếu approval, secret và kết quả hidden trước khi chốt ADR.`;
  const saving = decision.savingRate;
  $('saving-rate').textContent = saving === null ? '—' : `${num(Math.abs(saving) * 100, 1)}%`;
  $('saving-detail').textContent = saving === null ? 'Chưa đủ dữ liệu tính chênh lệch'
    : `${saving >= 0 ? 'Tiết kiệm' : 'Cao hơn'} so với ${names[baseline] ?? baseline}: ${num(Math.abs(decision.savingPerSuccess))} VND / thành công`;
  const claims = new Set(report.trials.map(trial => trial.claim_id));
  const seeds = new Set(report.trials.map(trial => trial.seed));
  $('experiment-context').textContent = `${Object.keys(report.by_shape).length} shape · ${claims.size} claim · ${seeds.size} seed · ${report.trials.length} lượt chạy ${decision.comparable ? '· Cùng bộ claim × seed' : '· Chưa xác nhận cùng bộ claim × seed'}`;
  const entries = Object.entries(report.by_shape);
  const maxCost = Math.max(0, ...entries.map(([, stats]) => typeof stats.cost_per_success_vnd === 'number' && Number.isFinite(stats.cost_per_success_vnd) ? stats.cost_per_success_vnd : 0));
  $('cost-chart').replaceChildren(); $('quality-chart').replaceChildren();
  for (const [shape, stats] of entries) {
    const winner = decision.winners.includes(shape);
    const costRow = element('div', undefined, `chart-row${winner ? ' is-winner' : ''}`);
    costRow.append(element('strong', `${names[shape] ?? shape}${winner ? ' ★' : ''}`, 'chart-name'), chartBar(stats.cost_per_success_vnd, maxCost, num(stats.cost_per_success_vnd), winner ? 'winner-fill' : 'cost-fill'));
    $('cost-chart').append(costRow);
    const qualityRow = element('div', undefined, 'chart-row');
    const bars = element('div', undefined, 'paired-bars');
    const pass = chartBar(stats.pass_rate, 1, percent(stats.pass_rate), 'pass-fill'); pass.setAttribute('aria-label', `Pass rate ${percent(stats.pass_rate)}`);
    const stable = chartBar(stats.pass_5, 1, percent(stats.pass_5), 'stable-fill'); stable.setAttribute('aria-label', `Pass⁵ ${percent(stats.pass_5)}`);
    bars.append(pass, stable); qualityRow.append(element('strong', names[shape] ?? shape, 'chart-name'), bars);
    $('quality-chart').append(qualityRow);
  }
}

function renderScenario() {
  const trials = state.benchmark.data.trials;
  populateSelect('seed-select', [...new Set(trials.filter(trial => trial.claim_id === $('claim-select').value).map(trial => trial.seed))].sort((a, b) => a-b));
  $('scenario-cards').replaceChildren();
  for (const shape of Object.keys(state.benchmark.data.by_shape)) {
    const trial = trials.find(item => item.shape === shape && item.claim_id === $('claim-select').value && String(item.seed) === $('seed-select').value);
    const card = element('article', undefined, 'scenario-card');
    card.append(element('h3', names[shape] ?? shape));
    if (!trial) { card.append(element('p', 'Chưa có lượt chạy tương ứng.')); }
    else {
      card.append(badge(trial.passed), element('strong', `${num(trial.cost_estimate)} VND`, 'scenario-cost'));
      const metrics = element('dl');
      for (const [label, value] of [['Trạng thái', trial.status ?? '—'], ['Số bước', num(trial.steps)], ['Lý do', trial.reason ?? '—']]) metrics.append(element('dt', label), element('dd', value));
      card.append(metrics, element('span', trial.run_id ?? '—', 'run-id'));
    }
    $('scenario-cards').append(card);
  }
}
function renderTrials() {
  const rows = filterTrials(state.benchmark.data.trials, $('shape-filter').value, $('result-filter').value);
  $('trials').replaceChildren();
  for (const trial of rows.slice(0, state.limit)) {
    const claim = element('div', trial.claim_id ?? '—');
    claim.append(element('span', trial.run_id ?? '—', 'run-id'));
    const tr = row([claim, names[trial.shape] ?? trial.shape, num(trial.seed, 0), badge(trial.passed), trial.status, trial.reason, num(trial.cost_estimate)]);
    tr.children[5].classList.add('reason'); $('trials').append(tr);
  }
  if (!rows.length) empty($('trials'), 7, 'Không có lần chạy phù hợp với bộ lọc.');
  $('trial-count').textContent = `Hiển thị ${Math.min(rows.length, state.limit)} / ${rows.length} lần chạy`;
  $('more').hidden = rows.length <= state.limit;
}
function renderCrash() {
  const data = state.crash.data;
  $('crash-score').textContent = `${data.passed}/${data.count}`;
  $('crash-count').textContent = `${data.count - data.passed} không đạt`;
  $('scenarios').replaceChildren();
  for (const scenario of data.scenarios) {
    const tr = row([scenario.id, scenario.point, badge(scenario.passed), scenario.reason]);
    tr.children[3].classList.add('reason'); $('scenarios').append(tr);
  }
  if (!data.scenarios.length) empty($('scenarios'), 4, 'Báo cáo chưa có kịch bản crash.');
}
function render() {
  const [title, description] = titles[state.view];
  $('page-title').textContent = title; $('page-description').textContent = description;
  $('benchmark-view').hidden = state.view !== 'benchmark'; $('crash-view').hidden = state.view !== 'crash';
  for (const button of document.querySelectorAll('[data-view]')) {
    const active = button.dataset.view === state.view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  }
  renderSource(); renderBenchmark(); renderCrash();
}
async function load(kind) {
  const path = `../reports/${kind === 'benchmark' ? 'benchmark' : 'crash'}.json`;
  try {
    const response = await fetch(path, {cache: 'no-store'});
    if (!response.ok) throw new Error(response.status === 404 ? 'Chưa có file báo cáo.' : `Không đọc được báo cáo (HTTP ${response.status}).`);
    const data = validateReport(kind, await response.json());
    state[kind] = {data, sample: false, source: `Nguồn: src/reports/${kind}.json · Nạp lúc ${new Date().toLocaleTimeString('vi-VN')}`};
  } catch (error) {
    // Preserve the last loaded real report if refresh fails.
    if (!state[kind]) state[kind] = {data: sample[kind], sample: true, source: ''};
    state[kind].source = `${error.message} ${state[kind].sample ? 'Đang dùng dữ liệu minh họa.' : 'Giữ báo cáo đã nạp trước đó.'} Có thể chọn file ${kind}.json để xem.`;
  }
}
async function reload() {
  if (state.busy) return;
  state.busy = true; $('reload').disabled = true; $('file').disabled = true;
  $('feedback').textContent = '';
  try {
    await Promise.all([load('benchmark'), load('crash')]);
    state.limit = 100; render();
  } finally {
    state.busy = false; $('reload').disabled = false; $('file').disabled = false;
  }
}
for (const button of document.querySelectorAll('[data-view]')) button.addEventListener('click', () => {
  state.view = button.dataset.view; $('feedback').textContent = '';
  if (state.benchmark && state.crash) render();
});
for (const id of ['shape-filter', 'result-filter']) $(id).addEventListener('change', () => {state.limit = 100; renderTrials();});
$('more').addEventListener('click', () => {state.limit += 100; renderTrials();});
for (const id of ['quality-threshold', 'baseline']) $(id).addEventListener('change', renderDecision);
for (const id of ['claim-select', 'seed-select']) $(id).addEventListener('change', renderScenario);
$('present').addEventListener('click', () => {
  const active = document.body.classList.toggle('presenting');
  $('present').setAttribute('aria-pressed', String(active));
  $('present').textContent = active ? 'Thoát trình bày' : 'Chế độ trình bày';
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.body.classList.contains('presenting')) $('present').click();
});
$('reload').addEventListener('click', reload);
$('file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  const kind = state.view;
  try {
    const data = validateReport(kind, JSON.parse(await file.text()));
    state[kind] = {data, sample: false, source: `File đã chọn: ${file.name} · Nạp lúc ${new Date().toLocaleTimeString('vi-VN')}`};
    state.limit = 100; $('feedback').textContent = ''; render();
  } catch (error) { $('feedback').textContent = `Không thể nạp ${file.name}: ${error.message}`; }
  event.target.value = '';
});
reload();

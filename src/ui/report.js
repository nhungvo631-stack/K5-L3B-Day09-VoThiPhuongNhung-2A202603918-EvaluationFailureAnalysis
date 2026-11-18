const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
export function validateReport(kind, data) {
  let valid = object(data);
  if (kind === 'benchmark') {
    valid &&= object(data.by_shape) && Array.isArray(data.trials)
      && Object.values(data.by_shape).every(object)
      && data.trials.every(row => object(row) && typeof row.shape === 'string' && [true, false, null].includes(row.passed));
  } else {
    valid &&= Number.isInteger(data.count) && data.count >= 0
      && Number.isInteger(data.passed) && data.passed >= 0 && data.passed <= data.count
      && Array.isArray(data.scenarios) && data.scenarios.length === data.count
      && data.scenarios.every(row => object(row) && typeof row.passed === 'boolean')
      && data.scenarios.filter(row => row.passed).length === data.passed;
  }
  if (!valid) throw new Error(`Sai cấu trúc ${kind}. Hãy chọn file do lab8.${kind === 'crash' ? 'crash_test' : 'benchmark'} tạo.`);
  return data;
}
export function filterTrials(rows, shape = 'all', result = 'all') {
  return rows.filter(row => (shape === 'all' || row.shape === shape)
    && (result === 'all' || (result === 'passed' ? row.passed === true : result === 'failed' ? row.passed === false : row.passed == null)));
}
export function formatNumber(value, digits = 2) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('vi-VN', {maximumFractionDigits: digits}).format(value) : '—';
}

// Economic shortlist only: approval/secret safety needs separate evidence.
export function compareShapes(report, minimumPass = 1, baseline = 'single') {
  const entries = Object.entries(report.by_shape);
  const signatures = entries.map(([shape]) => report.trials.filter(row => row.shape === shape)
    .map(row => JSON.stringify([row.claim_id, row.seed])).sort());
  const comparable = entries.length >= 2 && signatures.every(keys => keys.length > 0
    && new Set(keys).size === keys.length && JSON.stringify(keys) === JSON.stringify(signatures[0]));
  const candidates = comparable ? entries.filter(([shape, stats]) => {
    const rows = report.trials.filter(row => row.shape === shape);
    const graded = rows.filter(row => typeof row.passed === 'boolean');
    return stats.trials === rows.length && stats.graded_trials === rows.length && graded.length === rows.length
      && typeof stats.pass_rate === 'number' && stats.pass_rate >= minimumPass && stats.pass_rate <= 1
      && Math.abs(graded.filter(row => row.passed).length / rows.length - stats.pass_rate) < 1e-9
      && typeof stats.cost_per_success_vnd === 'number' && Number.isFinite(stats.cost_per_success_vnd) && stats.cost_per_success_vnd >= 0;
  }) : [];
  const cost = candidates.length ? Math.min(...candidates.map(([, stats]) => stats.cost_per_success_vnd)) : null;
  const winners = candidates.filter(([, stats]) => Math.abs(stats.cost_per_success_vnd - cost) < 1e-9).map(([shape]) => shape);
  const baselineCost = report.by_shape[baseline]?.cost_per_success_vnd;
  const hasBaseline = typeof baselineCost === 'number' && Number.isFinite(baselineCost) && baselineCost >= 0;
  const savingPerSuccess = cost !== null && hasBaseline ? baselineCost - cost : null;
  return {comparable, winners, cost, savingPerSuccess,
    savingRate: savingPerSuccess !== null && baselineCost > 0 ? savingPerSuccess / baselineCost : null};
}

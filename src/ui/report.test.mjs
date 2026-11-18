import test from 'node:test';
import assert from 'node:assert/strict';
import {validateReport, filterTrials, formatNumber, compareShapes} from './report.js';

test('accepts benchmark with ungraded trials without treating null as zero', () => {
  const report = {by_shape: {single: {pass_rate: null}}, trials: [{shape: 'single', passed: null}]};
  assert.equal(validateReport('benchmark', report), report);
  assert.equal(formatNumber(null), '—');
  assert.equal(formatNumber(0), '0');
});
test('filters failed trials separately from ungraded trials', () => {
  const rows = [{shape: 'single', passed: null}, {shape: 'single', passed: false}, {shape: 'workflow', passed: true}];
  assert.deepEqual(filterTrials(rows, 'single', 'failed'), [rows[1]]);
  assert.deepEqual(filterTrials(rows, 'all', 'ungraded'), [rows[0]]);
});
test('rejects malformed JSON structures with actionable errors', () => {
  for (const data of [null, [], {}, {by_shape: {}, trials: [null]}]) {
    assert.throws(() => validateReport('benchmark', data), /benchmark/);
  }
  assert.throws(() => validateReport('crash', {count: 20, passed: 21, scenarios: []}), /crash/);
  assert.throws(() => validateReport('crash', {count: 1, passed: 1, scenarios: [{passed: 'true'}]}), /crash/);
});
test('accepts crash reports including failed scenarios', () => {
  const report = {count: 2, passed: 1, crash_safety: '1/2', scenarios: [{id: 'CR-01', passed: true}, {id: 'CR-02', passed: false}]};
  assert.equal(validateReport('crash', report), report);
});

const comparisonReport = () => ({
  by_shape: {
    workflow: {pass_rate: 1, pass_5: 1, trials: 2, graded_trials: 2, cost_per_success_vnd: 10},
    single: {pass_rate: 1, pass_5: 1, trials: 2, graded_trials: 2, cost_per_success_vnd: 20},
    swarm: {pass_rate: 0.5, pass_5: 0, trials: 2, graded_trials: 2, cost_per_success_vnd: 5},
  },
  trials: ['workflow', 'single', 'swarm'].flatMap(shape => [11, 22].map(seed => ({shape, claim_id: 'C-001', seed, passed: shape !== 'swarm' || seed === 11}))),
});
test('chooses cheapest qualifying shape, not cheapest failing shape', () => {
  const result = compareShapes(comparisonReport(), 1, 'single');
  assert.deepEqual(result.winners, ['workflow']);
  assert.equal(result.savingRate, 0.5);
  assert.equal(result.savingPerSuccess, 10);
  assert.deepEqual(compareShapes(comparisonReport(), 0.5, 'single').winners, ['swarm']);
});
test('does not recommend across unmatched claims, seeds or ungraded trials', () => {
  const report = comparisonReport();
  report.trials[0].seed = 99;
  assert.equal(compareShapes(report, 1, 'single').comparable, false);
  assert.deepEqual(compareShapes(report, 1, 'single').winners, []);
  const ungraded = comparisonReport();
  ungraded.by_shape.workflow.graded_trials = 0;
  ungraded.by_shape.workflow.pass_rate = null;
  assert.deepEqual(compareShapes(ungraded, 1, 'single').winners, ['single']);
});
test('preserves ties and zero costs, avoids fabricated savings with missing baseline', () => {
  const report = comparisonReport();
  report.by_shape.workflow.cost_per_success_vnd = 0;
  report.by_shape.single.cost_per_success_vnd = 0;
  assert.deepEqual(compareShapes(report, 1, 'single').winners, ['workflow', 'single']);
  assert.equal(compareShapes(report, 1, 'single').savingRate, null);
  assert.equal(compareShapes(report, 1, 'missing').savingPerSuccess, null);
});

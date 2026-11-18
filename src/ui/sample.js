// Illustrative UI fixtures only. Never used as submission evidence.
const shapes = ['workflow', 'single', 'orchestrator', 'swarm'];
export const benchmark = {
  controlled_variables: {seeds: [11, 22, 33, 44, 55], model_backend: 'MockLLM', latency: 'unavailable', pricing: {simulated: true, currency: 'VND'}},
  by_shape: Object.fromEntries(shapes.map((shape, index) => [shape, {
    trials: 10, graded_trials: 10, pass_rate: (10-index)/10, pass_5: index ? 0.5 : 1,
    cost_per_success_vnd: [24, 125, 188, 220][index], mean_steps: [4, 6.2, 7.4, 9][index],
    seed_variance: [0, 0.01, 0.02, 0.04][index], mean_model_calls: index * 2, mean_tool_calls: 4+index,
  }])),
  trials: shapes.flatMap((shape, index) => Array.from({length: 10}, (_, i) => ({
    shape, claim_id: `DEMO-${Math.floor(i/5)+1}`, seed: [11,22,33,44,55][i%5],
    passed: i >= index, reason: i >= index ? 'ok' : 'demo_failure', status: i >= index ? 'completed' : 'error',
    cost_estimate: [24,112.5,150.4,154][index], steps: 4+index,
    run_id: `demo-${shape}-${i+1}`,
  }))),
};
export const crash = {
  count: 20, passed: 19, crash_safety: '19/20',
  scenarios: Array.from({length: 20}, (_, i) => ({id: `CR-${String(i+1).padStart(2, '0')}`,
    point: i < 5 ? 'before_effect' : i < 12 ? 'after_effect_before_checkpoint' : i < 17 ? 'after_checkpoint' : ['amount_conflict_on_retry', 'retry_without_approval', 'swarm_after_effect_before_checkpoint'][i-17],
    passed: i !== 19, reason: i === 19 ? 'Lỗi minh họa để xem trạng thái thất bại' : 'ok',
  })),
};

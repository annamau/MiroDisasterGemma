import service from './index'

export const auroraApi = {
  listScenarios() {
    return service.get('/api/scenario/list')
  },
  loadScenario(scenarioId, force = false) {
    return service.post('/api/scenario/load', {
      scenario_id: scenarioId,
      force_rebuild: force,
    })
  },
  baselineLoss(scenarioId) {
    return service.post(`/api/scenario/${scenarioId}/baseline_loss`)
  },
  listInterventions() {
    return service.get('/api/scenario/interventions')
  },
  runMonteCarlo(scenarioId, payload) {
    return service.post(`/api/scenario/${scenarioId}/run_mc`, payload)
  },
  // P-V3 streaming: kicks off a background MC, returns {run_id} immediately
  runMCStreaming(scenarioId, payload) {
    return service.post(`/api/scenario/${scenarioId}/run_mc`, {
      ...payload,
      streaming: true,
    })
  },
  getMCProgress(scenarioId, runId) {
    return service.get(`/api/scenario/${scenarioId}/run_mc/${runId}/progress`)
  },
  getMCResult(scenarioId, runId) {
    return service.get(`/api/scenario/${scenarioId}/run_mc/${runId}/result`)
  },
}

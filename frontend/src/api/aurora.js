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
}

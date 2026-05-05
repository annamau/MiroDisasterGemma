// SPDX-License-Identifier: Apache-2.0
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
  // M2.1: pure in-memory build of a reference scenario (no Neo4j touch).
  // Returns the full Scenario.to_dict() — buildings/districts/facilities
  // with lat/lon. Used by SchematicMap.
  previewScenario(scenarioId) {
    return service.get(`/api/scenario/${scenarioId}/preview`)
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

/**
 * U1 — axios interceptor shape contract test.
 *
 * The mc-progress-panel tests mock at the auroraApi layer (the established
 * pattern from P-V3). That's correct + clean, but it doesn't exercise the
 * actual axios interceptor at frontend/src/api/index.js:24-34.
 *
 * This test pins the interceptor's contract: given a backend that responds
 * with `{success: true, data: {...}}`, the consumer of `service.get()`
 * receives the OUTER envelope `{success: true, data: {...}}` directly
 * (the interceptor unwraps `response.data` once, NOT twice). If a future PR
 * accidentally changes the interceptor to return `response` (no unwrap) or
 * `response.data.data` (double unwrap), this test fails — and the
 * mc-progress-panel destructure would break in production.
 *
 * Tests at this layer mock the underlying `axios.create()` so we exercise
 * the real interceptor.use() handler.
 */

import { describe, it, expect, vi } from 'vitest'

// Mock axios BEFORE importing the service module, so the create() mock takes effect.
const mockGet = vi.fn()
const mockPost = vi.fn()
const interceptorHandlers = { request: null, response: null, responseError: null }

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get: mockGet,
      post: mockPost,
      interceptors: {
        request: { use: (handler) => { interceptorHandlers.request = handler } },
        response: {
          use: (handler, errHandler) => {
            interceptorHandlers.response = handler
            interceptorHandlers.responseError = errHandler
          },
        },
      },
    })),
  },
}))

// Now import — the interceptor handlers register on import.
await import('@/api/index.js')

describe('axios response interceptor', () => {
  it('returns response.data unwrapped when success is true', () => {
    const fakeResponse = {
      data: { success: true, data: { arms: { foo: 1 }, done: false } },
    }
    const result = interceptorHandlers.response(fakeResponse)
    // The interceptor MUST return the outer envelope `{success, data}` — NOT `response` and NOT `response.data.data`.
    expect(result).toEqual({ success: true, data: { arms: { foo: 1 }, done: false } })
    // Defense-in-depth assertions: explicit shape pinning.
    expect(result.success).toBe(true)
    expect(result.data).toBeDefined()
    expect(result.data.arms.foo).toBe(1)
  })

  it('rejects when success is false', async () => {
    const fakeResponse = {
      data: { success: false, error: 'simulated backend failure' },
    }
    await expect(
      Promise.resolve(interceptorHandlers.response(fakeResponse))
    ).rejects.toThrow('simulated backend failure')
  })

  it('passes through when success key is absent (backwards compat)', () => {
    // Some legacy endpoints may not wrap in {success, data}. The interceptor
    // returns the unwrapped `response.data` as-is when `success` is undefined.
    const fakeResponse = { data: { foo: 'bar' } }
    const result = interceptorHandlers.response(fakeResponse)
    expect(result).toEqual({ foo: 'bar' })
  })
})

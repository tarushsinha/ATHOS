import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request } from './client'
import { clearToken, setToken } from '../auth/tokenStore'

describe('api client', () => {
  beforeEach(() => {
    clearToken()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('attaches Authorization header when auth=true', async () => {
    setToken('my-token')
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'x-request-id': 'req-auth' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await request('/v1/auth/me', { auth: true })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    const headers = init.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer my-token')
  })

  it('attaches X-Client-Timezone header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'x-request-id': 'req-tz' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await request('/health')

    const init = fetchMock.mock.calls[0][1] as RequestInit
    const headers = init.headers as Headers
    expect(headers.get('X-Client-Timezone')).toBeTruthy()
  })

  it('returns X-Request-ID from response headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'x-request-id': 'req-123' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await request<{ status: string }>('/health')

    expect(result.requestId).toBe('req-123')
    expect(result.data.status).toBe('ok')
  })

  it('throws ApiError with requestId on 401', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid credentials' }), {
        status: 401,
        headers: { 'X-Request-ID': 'test-req-id' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    try {
      await request('/v1/auth/login', {
        method: 'POST',
        body: { email: 'bad@example.com', password: 'wrongpass' },
      })
      throw new Error('Expected request to throw')
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      const apiErr = err as ApiError
      expect(apiErr.status).toBe(401)
      expect(apiErr.requestId).toBe('test-req-id')
      expect(apiErr.detail).toBe('Invalid credentials')
    }
  })
})

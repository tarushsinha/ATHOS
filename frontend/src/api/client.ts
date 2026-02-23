import { API_BASE_URL } from '../config'
import { getToken } from '../auth/tokenStore'

type RequestOptions = {
  method?: string
  body?: unknown
  auth?: boolean
}

export type RequestResult<T> = {
  data: T
  requestId: string | null
}

export class ApiError extends Error {
  status: number
  requestId: string | null
  detail: string
  responseBody?: unknown
  data?: unknown

  constructor(status: number, requestId: string | null, detail: string, responseBody?: unknown) {
    super(detail)
    this.status = status
    this.requestId = requestId
    this.detail = detail
    this.responseBody = responseBody
    this.data = responseBody
  }
}

function getClientTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

function getRequestId(headers: Headers): string | null {
  return headers.get('x-request-id') ?? headers.get('X-Request-ID')
}

function parseResponseBody(text: string): unknown {
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

export async function request<T>(
  path: string,
  { method = 'GET', body, auth = false }: RequestOptions = {},
): Promise<RequestResult<T>> {
  const headers = new Headers()
  headers.set('X-Client-Timezone', getClientTimezone())

  if (body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  if (auth) {
    const token = getToken()
    if (!token) {
      throw new ApiError(401, null, 'Missing token', { detail: 'Missing token' })
    }
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  const requestId = getRequestId(response.headers)
  const text = await response.text()
  const parsed = parseResponseBody(text)

  if (!response.ok) {
    const detail =
      typeof parsed === 'object' &&
      parsed !== null &&
      'detail' in parsed &&
      typeof (parsed as { detail?: unknown }).detail === 'string'
        ? (parsed as { detail: string }).detail
        : `Request failed with status ${response.status}`
    throw new ApiError(response.status, requestId, detail, parsed)
  }

  return {
    data: parsed as T,
    requestId,
  }
}

import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, request } from '../api/client'

function getTodayDateString() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function DashboardPage() {
  const [date, setDate] = useState(getTodayDateString())
  const [requestId, setRequestId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [responseText, setResponseText] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)

    try {
      const result = await request<unknown>(`/v1/dashboard/day?date=${encodeURIComponent(date)}`, {
        auth: true,
      })
      setRequestId(result.requestId)
      setResponseText(JSON.stringify(result.data, null, 2))
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = (err.data as { detail?: string } | null)?.detail
        setError(detail ?? `Request failed (${err.status})`)
        setRequestId(err.requestId)
      } else {
        setError('Unexpected error')
      }
    } finally {
      setLoading(false)
    }
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await loadDashboard()
  }

  return (
    <section className='panel'>
      <h2>Dashboard Day</h2>
      <form onSubmit={onSubmit} className='inline-form'>
        <label>
          Date
          <input type='date' required value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        <button type='submit' disabled={loading}>
          {loading ? 'Loading...' : 'Load'}
        </button>
      </form>
      {error && <p className='error'>{error}</p>}
      {responseText && (
        <pre className='json-box' aria-label='dashboard-response-json'>
          {responseText}
        </pre>
      )}
      <p className='meta'>Last X-Request-ID: {requestId ?? 'n/a'}</p>
    </section>
  )
}

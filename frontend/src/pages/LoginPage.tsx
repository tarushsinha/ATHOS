import { useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { request, ApiError } from '../api/client'
import { setToken } from '../auth/tokenStore'

type LoginResponse = {
  access_token: string
  token_type: string
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [requestId, setRequestId] = useState<string | null>(null)

  const redirectTo = typeof location.state?.from === 'string' ? location.state.from : '/dashboard'

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const result = await request<LoginResponse>('/v1/auth/login', {
        method: 'POST',
        body: { email, password },
      })
      setToken(result.data.access_token)
      setRequestId(result.requestId)
      navigate(redirectTo, { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || `Login failed (${err.status})`)
        setRequestId(err.requestId)
      } else {
        setError('Unexpected error')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className='panel'>
      <h2>Login</h2>
      <form onSubmit={onSubmit} className='form-grid'>
        <label>
          Email
          <input
            type='email'
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete='username'
          />
        </label>
        <label>
          Password
          <input
            type='password'
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete='current-password'
          />
        </label>
        <button type='submit' disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>
      {error && <p className='error'>{error}</p>}
      <p className='meta'>Last X-Request-ID: {requestId ?? 'n/a'}</p>
    </section>
  )
}

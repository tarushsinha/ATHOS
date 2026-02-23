import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { getToken } from './tokenStore'

type RequireAuthProps = {
  children: ReactNode
}

export function RequireAuth({ children }: RequireAuthProps) {
  const location = useLocation()
  const token = getToken()

  if (!token) {
    return <Navigate to='/login' replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}

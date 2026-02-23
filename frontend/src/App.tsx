import { Navigate, NavLink, Outlet, Route, Routes, useNavigate } from 'react-router-dom'
import { clearToken, getToken } from './auth/tokenStore'
import { RequireAuth } from './auth/RequireAuth'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { WorkoutPage } from './pages/WorkoutPage'

function AppLayout() {
  const navigate = useNavigate()
  const token = getToken()

  const onSignout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <div className='app-shell'>
      <header className='top-bar'>
        <h1>ATHOS</h1>
        <nav>
          <NavLink to='/dashboard'>Dashboard</NavLink>
          <NavLink to='/workout'>Workout</NavLink>
          {!token && <NavLink to='/login'>Login</NavLink>}
        </nav>
        {token && (
          <button type='button' onClick={onSignout}>
            Sign out
          </button>
        )}
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path='/login' element={<LoginPage />} />
        <Route
          path='/workout'
          element={
            <RequireAuth>
              <WorkoutPage />
            </RequireAuth>
          }
        />
        <Route
          path='/dashboard'
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route path='/' element={<Navigate to={getToken() ? '/dashboard' : '/login'} replace />} />
      </Route>
    </Routes>
  )
}

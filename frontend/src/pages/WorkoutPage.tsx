import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, request } from '../api/client'

type WorkoutType = '' | 'STRENGTH' | 'CARDIO'

type StrengthSetRow = {
  exercise_name: string
  weight: string
  reps: string
}

type WorkoutCreateResponse = {
  workout_id: string
  workout_type: 'STRENGTH' | 'CARDIO' | 'OTHER'
  strength_set_count: number
  cardio_session_created: boolean
}

function toIsoOrUndefined(dateTimeLocal: string): string | undefined {
  if (!dateTimeLocal) return undefined
  const date = new Date(dateTimeLocal)
  if (Number.isNaN(date.getTime())) return undefined
  return date.toISOString()
}

function metersToMiles(value: number): number {
  return value / 1609.344
}

export function WorkoutPage() {
  const [workoutType, setWorkoutType] = useState<WorkoutType>('')
  const [title, setTitle] = useState('')
  const [startTs, setStartTs] = useState('')
  const [strengthSets, setStrengthSets] = useState<StrengthSetRow[]>([
    { exercise_name: '', weight: '', reps: '' },
  ])
  const [activityType, setActivityType] = useState('')
  const [durationSeconds, setDurationSeconds] = useState('')
  const [distanceM, setDistanceM] = useState('')
  const [avgHr, setAvgHr] = useState('')
  const [calories, setCalories] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  const [responseData, setResponseData] = useState<WorkoutCreateResponse | null>(null)

  const workoutId = responseData?.workout_id ?? null
  const responseJson = useMemo(() => {
    if (!responseData) return null
    return JSON.stringify(responseData, null, 2)
  }, [responseData])

  const updateSet = (index: number, key: keyof StrengthSetRow, value: string) => {
    setStrengthSets((prev) => prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)))
  }

  const addSetRow = () => {
    setStrengthSets((prev) => [...prev, { exercise_name: '', weight: '', reps: '' }])
  }

  const removeSetRow = (index: number) => {
    setStrengthSets((prev) => (prev.length === 1 ? prev : prev.filter((_, i) => i !== index)))
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    setResponseData(null)

    try {
      const startTsIso = toIsoOrUndefined(startTs)
      if (startTs && !startTsIso) {
        setError('Invalid start time')
        return
      }

      if (workoutType === 'STRENGTH') {
        const cleanedSets = strengthSets
          .map((row) => ({
            exercise_name: row.exercise_name.trim(),
            weight: row.weight.trim() === '' ? undefined : Number(row.weight),
            reps: row.reps.trim() === '' ? undefined : Number(row.reps),
          }))
          .filter((row) => row.exercise_name !== '')

        if (cleanedSets.length === 0) {
          setError('Add at least one strength set with an exercise name.')
          return
        }

        const payload: Record<string, unknown> = {
          workout_type: 'STRENGTH',
          title: title.trim() || undefined,
          strength_sets: cleanedSets,
          client_uuid: crypto.randomUUID(),
        }

        if (startTsIso) payload.start_ts = startTsIso

        const result = await request<WorkoutCreateResponse>('/v1/workouts', {
          method: 'POST',
          body: payload,
          auth: true,
        })
        setResponseData(result.data)
        setRequestId(result.requestId)
        return
      }

      if (workoutType === 'CARDIO') {
        if (!activityType.trim()) {
          setError('Activity type is required for cardio.')
          return
        }
        if (!durationSeconds.trim()) {
          setError('Duration seconds is required for cardio.')
          return
        }

        const durationValue = Number(durationSeconds)
        if (!Number.isFinite(durationValue) || durationValue < 0) {
          setError('Duration seconds must be a non-negative number.')
          return
        }

        const notesParts = [
          `activity_type=${activityType.trim()}`,
          avgHr.trim() ? `avg_hr=${avgHr.trim()}` : null,
          calories.trim() ? `calories=${calories.trim()}` : null,
        ].filter(Boolean)

        const payload: Record<string, unknown> = {
          workout_type: 'CARDIO',
          title: title.trim() || activityType.trim(),
          cardio_session: {
            duration_seconds: durationValue,
            distance_miles: distanceM.trim() ? metersToMiles(Number(distanceM)) : undefined,
            notes: notesParts.join('; '),
          },
          client_uuid: crypto.randomUUID(),
        }

        if (startTsIso) payload.start_ts = startTsIso

        const result = await request<WorkoutCreateResponse>('/v1/workouts', {
          method: 'POST',
          body: payload,
          auth: true,
        })
        setResponseData(result.data)
        setRequestId(result.requestId)
        return
      }

      setError('Select a workout type.')
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = (err.data as { detail?: string } | null)?.detail
        setError(detail ?? `Request failed (${err.status})`)
        setRequestId(err.requestId)
      } else {
        setError('Unexpected error')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className='panel'>
      <h2>Workout Entry</h2>
      <form onSubmit={onSubmit} className='form-grid'>
        <fieldset>
          <legend>Workout Type</legend>
          <label>
            <input
              type='radio'
              name='workoutType'
              value='STRENGTH'
              checked={workoutType === 'STRENGTH'}
              onChange={() => setWorkoutType('STRENGTH')}
            />
            Strength
          </label>
          <label>
            <input
              type='radio'
              name='workoutType'
              value='CARDIO'
              checked={workoutType === 'CARDIO'}
              onChange={() => setWorkoutType('CARDIO')}
            />
            Cardio
          </label>
        </fieldset>

        <label>
          Title
          <input type='text' value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>

        <label>
          Start Time (optional)
          <input
            type='datetime-local'
            value={startTs}
            onChange={(event) => setStartTs(event.target.value)}
          />
        </label>

        {workoutType === 'STRENGTH' && (
          <div className='subsection'>
            <h3>Strength Sets</h3>
            {strengthSets.map((row, index) => (
              <div key={`${index}-${row.exercise_name}`} className='set-row'>
                <input
                  type='text'
                  placeholder='exercise_name'
                  value={row.exercise_name}
                  onChange={(event) => updateSet(index, 'exercise_name', event.target.value)}
                />
                <input
                  type='number'
                  step='any'
                  min='0'
                  placeholder='weight'
                  value={row.weight}
                  onChange={(event) => updateSet(index, 'weight', event.target.value)}
                />
                <input
                  type='number'
                  min='0'
                  placeholder='reps'
                  value={row.reps}
                  onChange={(event) => updateSet(index, 'reps', event.target.value)}
                />
                <button type='button' onClick={() => removeSetRow(index)}>
                  Remove
                </button>
              </div>
            ))}
            <button type='button' onClick={addSetRow}>
              Add Set
            </button>
          </div>
        )}

        {workoutType === 'CARDIO' && (
          <div className='subsection'>
            <h3>Cardio Session</h3>
            <label>
              Activity Type
              <input
                type='text'
                value={activityType}
                onChange={(event) => setActivityType(event.target.value)}
              />
            </label>
            <label>
              Duration (seconds)
              <input
                type='number'
                min='0'
                value={durationSeconds}
                onChange={(event) => setDurationSeconds(event.target.value)}
              />
            </label>
            <label>
              Distance (meters, optional)
              <input
                type='number'
                step='any'
                min='0'
                value={distanceM}
                onChange={(event) => setDistanceM(event.target.value)}
              />
            </label>
            <label>
              Avg HR (optional)
              <input type='number' min='0' value={avgHr} onChange={(event) => setAvgHr(event.target.value)} />
            </label>
            <label>
              Calories (optional)
              <input
                type='number'
                min='0'
                value={calories}
                onChange={(event) => setCalories(event.target.value)}
              />
            </label>
          </div>
        )}

        <button type='submit' disabled={submitting}>
          {submitting ? 'Submitting...' : 'Submit Workout'}
        </button>
      </form>
      {error && <p className='error'>{error}</p>}
      {workoutId && <p>Workout ID: {workoutId}</p>}
      {responseJson && (
        <pre className='json-box' aria-label='workout-response-json'>
          {responseJson}
        </pre>
      )}
      <p className='meta'>Last X-Request-ID: {requestId ?? 'n/a'}</p>
    </section>
  )
}

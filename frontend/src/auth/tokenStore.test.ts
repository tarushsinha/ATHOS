import { beforeEach, describe, expect, it } from 'vitest'
import { clearToken, getToken, setToken } from './tokenStore'

describe('tokenStore', () => {
  beforeEach(() => {
    clearToken()
  })

  it('sets and gets token', () => {
    setToken('abc123')
    expect(getToken()).toBe('abc123')
  })

  it('clears token', () => {
    setToken('abc123')
    clearToken()
    expect(getToken()).toBeNull()
  })
})

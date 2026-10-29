import { createContext, useContext, useState, useCallback } from 'react'
import { api, setToken, USING_MOCK } from '../api/index.js'

/* Status label/colour map used by StatusBadge in ui.jsx. */
export const STATUS_META = {
  new: { label: 'New', cls: 'b-new' },
  quoted: { label: 'Quoted', cls: 'b-quote' },
  closed: { label: 'Closed', cls: 'b-ok' },
  sent: { label: 'Sent', cls: 'b-ok' },
  pending: { label: 'Pending', cls: 'b-pend' },
}

const Ctx = createContext(null)
export const useStore = () => useContext(Ctx)

export function StoreProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('vg_user') || 'null') } catch { return null }
  })
  const [toast, setToast] = useState(null)

  const flash = useCallback((msg, kind = 'ok') => {
    setToast({ msg, kind })
    setTimeout(() => setToast(null), 2600)
  }, [])

  const login = async (username, password) => {
    try {
      const { token, user: u } = await api.login(username, password)
      setToken(token)
      try { localStorage.setItem('vg_user', JSON.stringify(u)) } catch { /* ignore */ }
      setUser(u)
      return true
    } catch {
      return false
    }
  }

  const logout = () => {
    setToken('')
    try { localStorage.removeItem('vg_user') } catch { /* ignore */ }
    setUser(null)
  }

  return (
    <Ctx.Provider value={{ user, auth: !!user, toast, flash, login, logout, api, usingMock: USING_MOCK }}>
      {children}
    </Ctx.Provider>
  )
}

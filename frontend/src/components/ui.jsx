import { useState } from 'react'
import { useStore, STATUS_META } from '../store/useStore.jsx'

export function isWithinDateRange(timestamp, range) {
  if (!range) return true
  const { fromDate, toDate } = range
  if (!fromDate && !toDate) return true
  if (!timestamp) return false
  const t = typeof timestamp === 'number' ? timestamp : new Date(timestamp).getTime()
  if (isNaN(t)) return false

  if (fromDate) {
    const from = new Date(`${fromDate}T00:00:00`).getTime()
    if (t < from) return false
  }
  if (toDate) {
    const to = new Date(`${toDate}T23:59:59.999`).getTime()
    if (t > to) return false
  }
  return true
}

export function DateFilter({ onFilter, onReset }) {
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [isActive, setIsActive] = useState(false)

  const handleSearch = (e) => {
    e?.preventDefault()
    if (fromDate || toDate) {
      setIsActive(true)
      onFilter?.({ fromDate, toDate })
    } else {
      setIsActive(false)
      onFilter?.(null)
    }
  }

  const handleCancel = () => {
    setFromDate('')
    setToDate('')
    setIsActive(false)
    if (onReset) {
      onReset()
    } else {
      onFilter?.(null)
    }
  }

  return (
    <form className="date-filter-bar" onSubmit={handleSearch}>
      <div className="date-filter-group">
        <label>From Date</label>
        <input
          type="date"
          className="date-input"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
        />
      </div>
      <div className="date-filter-group">
        <label>To Date</label>
        <input
          type="date"
          className="date-input"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
        />
      </div>
      <div className="date-filter-buttons">
        <button type="submit" className="btn btn-primary btn-sm date-btn-search">
          <span>🔍</span> Search
        </button>
        <button type="button" className="btn btn-outline btn-sm date-btn-cancel" onClick={handleCancel}>
          <span>✕</span> Cancel
        </button>
      </div>
      {isActive && (
        <span className="badge b-ok date-filter-badge">
          Filtered: {fromDate || 'Start'} → {toDate || 'Now'}
        </span>
      )}
    </form>
  )
}

export function StatusBadge({ status }) {
  const m = STATUS_META[status] || { label: status, cls: 'b-muted' }
  return <span className={`badge ${m.cls}`}>{m.label}</span>
}

export function PropStatusBadge({ status }) {
  const map = {
    pending_approval: ['b-pend', 'Pending Approval'],
    sent: ['b-ok', 'Buyer Proposal Sent'],
    rejected: ['b-reject', 'Rejected'],
    draft: ['b-muted', 'Draft'],
  }
  const [cls, label] = map[status] || ['b-muted', status]
  return <span className={`badge ${cls}`}>{label}</span>
}

export const money = (n, c = 'INR') =>
  `${c === 'INR' ? '₹' : c + ' '}${Number(n || 0).toLocaleString('en-IN')}`

// Amount without the currency symbol (used when the ₹ sits in the column header).
export const num = (n) => Number(n || 0).toLocaleString('en-IN')

export function Empty({ icon = '📭', title, sub, action }) {
  return (
    <div className="empty">
      <div className="big">{icon}</div>
      <h3 style={{ margin: '0 0 6px' }}>{title}</h3>
      {sub && <p className="muted" style={{ margin: 0 }}>{sub}</p>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  )
}

export function Modal({ title, children, onClose, wide, full }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={'modal' + (full ? ' modal-full' : wide ? ' modal-wide' : '')} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

export function Toast() {
  const { toast } = useStore()
  if (!toast) return null
  return <div className={`toast ${toast.kind}`} role="status">{toast.msg}</div>
}

export function ago(ts) {
  const n = typeof ts === 'number' ? ts : Date.parse(ts)
  const s = Math.floor((Date.now() - n) / 1000)
  if (!isFinite(s)) return ''
  if (s < 60) return 'just now'
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// Format a date string / ms as e.g. 22 Oct 2026.
export function fmtDate(x) {
  if (!x) return '—'
  const d = new Date(x)
  if (isNaN(d)) return '—'
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function SegBadge({ seg }) {
  const map = {
    everyone: ['b-muted', 'Everyone'], cold: ['b-new', 'Cold'],
    hot: ['b-quote', 'Hot'], very_hot: ['b-reject', 'Very Hot'],
  }
  const [cls, label] = map[seg] || ['b-muted', seg]
  return <span className={`badge ${cls}`}>{label}</span>
}

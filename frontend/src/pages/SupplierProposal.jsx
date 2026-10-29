import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/index.js'
import { useStore } from '../store/useStore.jsx'
import { money, num, fmtDate, DateFilter, Modal, SegBadge } from '../components/ui.jsx'

const SEGMENTS = [
  { v: 'everyone', label: 'Everyone' },
  { v: 'cold', label: 'Cold' },
  { v: 'hot', label: 'Hot' },
  { v: 'very_hot', label: 'Very Hot' },
]

/* Multi-select dropdown with checkboxes for the Buyer column */
function BuyerMultiSelect({ value, onChange }) {
  const [open, setOpen] = useState(false)

  const parseValue = (val) => {
    if (!val) return ['everyone']
    if (Array.isArray(val)) return val.map((s) => String(s).trim().toLowerCase())
    if (typeof val === 'string') {
      const parts = val.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean)
      return parts.length ? parts : ['everyone']
    }
    return [String(val).toLowerCase()]
  }

  const selected = parseValue(value)
  const isEveryone = selected.includes('everyone')

  const toggle = (v) => {
    let next = []
    if (v === 'everyone') {
      next = isEveryone ? [] : ['everyone']
    } else {
      const withoutEveryone = selected.filter((s) => s !== 'everyone')
      if (withoutEveryone.includes(v)) {
        next = withoutEveryone.filter((s) => s !== v)
      } else {
        next = [...withoutEveryone, v]
      }
      const specific = ['cold', 'hot', 'very_hot']
      if (specific.every((s) => next.includes(s))) {
        next = ['everyone']
      }
    }
    onChange(next.length ? next.join(',') : '')
  }

  const getLabel = () => {
    if (isEveryone || (!selected.length && value === 'everyone')) return 'Everyone'
    if (!selected.length) return 'Select buyer…'
    return selected
      .map((val) => {
        const found = SEGMENTS.find((s) => s.v === val)
        return found ? found.label : val
      })
      .join(', ')
  }

  return (
    <div className="col-menu" style={{ width: '100%', minWidth: 130 }}>
      <button
        type="button"
        className="cell-input"
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
          cursor: 'pointer',
          textAlign: 'left',
          background: '#fff',
        }}
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {getLabel()}
        </span>
        <span style={{ fontSize: 10, color: 'var(--muted)', flexShrink: 0 }}>▾</span>
      </button>

      {open && (
        <>
          <div className="col-menu-backdrop" style={{ zIndex: 40 }} onClick={() => setOpen(false)} />
          <div
            className="col-menu-pop"
            style={{
              minWidth: 160,
              boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
              borderRadius: 8,
              padding: '6px',
              zIndex: 41,
            }}
          >
            <div className="col-menu-title" style={{ padding: '2px 6px 6px', fontSize: 11, color: 'var(--muted)', fontWeight: 700 }}>
              Select target buyers:
            </div>
            {SEGMENTS.map((s) => {
              const checked = s.v === 'everyone' ? isEveryone : selected.includes(s.v)
              return (
                <label
                  key={s.v}
                  className="col-menu-item"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 8px',
                    borderRadius: 6,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(s.v)}
                    style={{ cursor: 'pointer', width: 15, height: 15, accentColor: 'var(--brand-600)' }}
                  />
                  <span>{s.label}</span>
                </label>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function EditableText({ value, onCommit }) {
  const [v, setV] = useState(value)
  const ref = useRef(value)
  useEffect(() => { setV(value); ref.current = value }, [value])
  return (
    <input className="cell-input" value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => { if (v !== ref.current) { ref.current = v; onCommit(v) } }}
      onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur() }} />
  )
}

const STATES = [
  { v: 'active', label: 'Active' },
  { v: 'sold', label: 'Sold' },
  { v: 'hold', label: 'Hold' },
]

export default function SupplierProposal() {
  const { flash } = useStore()
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [range, setRange] = useState(null)
  const [stateFilter, setStateFilter] = useState('active')
  const [busy, setBusy] = useState(null)
  const [sentModal, setSentModal] = useState(null)
  const [gallery, setGallery] = useState(null)
  const [confirmSend, setConfirmSend] = useState(null)

  const load = () => {
    setLoading(true)
    api.proposals({ q, from: range?.fromDate, to: range?.toDate, state: stateFilter })
      .then((d) => { setRows(d.rows || []); setLoading(false) })
      .catch((err) => {
        console.error('Failed to load proposals:', err)
        setLoading(false)
      })
  }
  useEffect(load, [q, range, stateFilter])

  // Auto-refresh: poll the backend every 30s (matching the server's fetch cadence)
  // so newly imported supplier quotes appear without a manual reload. A tick is
  // skipped while a cell is being edited or a modal is open, so in-progress input
  // is never clobbered. This refresh is silent (no loading spinner).
  useEffect(() => {
    const id = setInterval(() => {
      const ae = document.activeElement
      if (ae && ['INPUT', 'TEXTAREA', 'SELECT'].includes(ae.tagName)) return
      if (sentModal || gallery || confirmSend) return
      api.proposals({ q, from: range?.fromDate, to: range?.toDate, state: stateFilter })
        .then((d) => setRows(d.rows || []))
        .catch(() => {})
    }, 30000)
    return () => clearInterval(id)
  }, [q, range, stateFilter, sentModal, gallery, confirmSend])

  const patch = async (id, p) => {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...p } : r)))
    await api.updateProposal(id, p)
  }

  const setState = async (r, state) => {
    if (state === r.state) return
    await api.setProposalState(r.id, state)
    flash(`Marked ${state}`)
    // If it still matches the active filter keep it, otherwise drop it from view.
    setRows((rs) => (state === stateFilter
      ? rs.map((x) => (x.id === r.id ? { ...x, state } : x))
      : rs.filter((x) => x.id !== r.id)))
  }

  const getPhoto = async (r) => {
    setBusy(`photo-${r.id}`)
    try {
      const res = await api.requestPhoto(r.id)
      setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, photo_status: 'requested' } : x)))
      flash(`Photo request sent to ${r.supplier_name} on ${res.channel}`)
    } catch (err) {
      flash(err.message || 'Failed to request photo')
    } finally {
      setBusy(null)
    }
  }

  const askSend = async (r) => {
    setBusy(`send-${r.id}`)
    try {
      const info = await api.recipients(r.id)
      setConfirmSend({ row: r, ...info })
    } catch (err) {
      flash(err.message || 'Could not load recipients', 'err')
    } finally {
      setBusy(null)
    }
  }

  const doSend = async () => {
    const r = confirmSend.row
    setBusy(`send-${r.id}`)
    try {
      const res = await api.sendProposal(r.id)
      setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, status: 'sent' } : x)))
      setConfirmSend(null)
      setSentModal({ machine: r.machine, ...res })
      flash(`Quotation sent to ${res.sent || 0} buyer(s)`)
    } catch (err) {
      flash(err.message || 'Failed to send quotation', 'err')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="stack">
      <div className="page-actions">
        <div className="toolbar">
          <input className="search-input" placeholder="🔍 Search machine / supplier…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <DateFilter onFilter={setRange} onReset={() => setRange(null)} />
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Supplier Proposals — per machine</h3>
          <span className="hint">{rows.length} machine row(s){loading ? ' · loading…' : ''} · segregated from supplier emails</span>
        </div>
        <div className="card-pad" style={{ paddingBottom: 0 }}>
          <div className="tabs">
            {STATES.map((s) => (
              <button key={s.v} className={`tab${stateFilter === s.v ? ' active' : ''}`} onClick={() => setStateFilter(s.v)}>{s.label}</button>
            ))}
          </div>
        </div>
        <div className="table-wrap">
          <table className="dense">
            <thead>
              <tr>
                <th>S.No</th><th>Date</th><th>Supplier</th><th>Machine</th><th>Photos</th>
                <th style={{ textAlign: 'right' }}>Price (₹)</th><th>Margin %</th><th style={{ textAlign: 'right' }}>Final (₹)</th>
                <th>Buyer</th><th>Status</th><th>Photo request</th><th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const final = Math.round(Number(r.price) * (1 + Number(r.margin_pct) / 100))
                const isSent = r.status === 'sent' || r.quotation_sent
                return (
                  <tr key={r.id}>
                    <td className="t-sub">{i + 1}</td>
                    <td className="t-sub">{fmtDate(r.received_at || r.created_at)}</td>
                    <td className="t-main">{r.supplier_name}<div className="t-sub">{r.source_channel}</div></td>
                    <td style={{ textAlign: 'center' }}>
                      <button className="btn btn-outline btn-sm" style={{ padding: '4px 10px' }}
                        onClick={() => navigate(`/supplier-proposal/${r.id}`)} title={`View details — ${r.machine}`}>🔍</button>
                    </td>
                    <td>
                      {r.photos?.length
                        ? <button className="photo-chip" onClick={() => setGallery({ machine: r.machine, photos: r.photos })} title="View photos">
                            <img src={r.photos[0]} alt="" className="photo-thumb" />
                            {r.photos.length > 1 && <span className="photo-count">+{r.photos.length - 1}</span>}
                          </button>
                        : <span className="muted">—</span>}
                    </td>
                    <td className="money" style={{ textAlign: 'right' }}>{num(r.price)}</td>
                    <td style={{ width: 90 }}>
                      <input className="cell-input" type="number" value={r.margin_pct}
                        onChange={(e) => setRows((rs) => rs.map((x) => (x.id === r.id ? { ...x, margin_pct: e.target.value } : x)))}
                        onBlur={(e) => patch(r.id, { margin_pct: Number(e.target.value) })} />
                    </td>
                    <td className="money" style={{ color: 'var(--brand-700)', textAlign: 'right' }}>{num(final)}</td>
                    <td style={{ minWidth: 140 }}>
                      <BuyerMultiSelect value={r.buyer_segment} onChange={(val) => patch(r.id, { buyer_segment: val })} />
                    </td>
                    <td style={{ width: 110 }}>
                      <select className="cell-input" value={r.state || 'active'} onChange={(e) => setState(r, e.target.value)}>
                        <option value="active">Active</option>
                        <option value="sold">Sold</option>
                        <option value="hold">Hold</option>
                      </select>
                    </td>
                    <td>
                      <button className="btn btn-outline btn-sm" style={{ padding: '4px 8px' }} disabled={busy === `photo-${r.id}`} onClick={() => getPhoto(r)} title="Request photos">📷</button>
                      {r.photo_status === 'requested' && <div className="t-sub" style={{ color: 'var(--warn-600)' }}>requested</div>}
                    </td>
                    <td>
                      {isSent
                        ? <span className="badge b-ok" style={{ padding: '5px 10px', fontSize: 12, fontWeight: 700 }}>✓ Sent</span>
                        : <button className="btn btn-primary btn-sm" disabled={busy === `send-${r.id}`} onClick={() => askSend(r)}>{busy === `send-${r.id}` ? '…' : '➤ Send'}</button>}
                    </td>
                  </tr>
                )
              })}
              {!loading && !rows.length && <tr><td colSpan="12" className="muted" style={{ textAlign: 'center', padding: 30 }}>No {stateFilter} proposals found.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {sentModal && (
        <Modal title="Quotation Sent" onClose={() => setSentModal(null)}>
          <div className="stack">
            <p style={{ margin: 0 }}>
              Sent the <b>{sentModal.machine}</b> quotation to <b>{sentModal.sent}</b> buyer(s) who
              enquired for this machine, at <b className="money">{money(sentModal.amount)}</b> per unit —
              each on the channel they originally used.
            </p>
            <div className="modal-foot"><button className="btn btn-primary" onClick={() => setSentModal(null)}>Done</button></div>
          </div>
        </Modal>
      )}

      {gallery && (
        <Modal title={`Photos — ${gallery.machine}`} onClose={() => setGallery(null)}>
          <div className="photo-grid">
            {gallery.photos.map((src, i) => (
              <a key={i} href={src} target="_blank" rel="noreferrer" className="photo-grid-item">
                <img src={src} alt={`photo ${i + 1}`} />
              </a>
            ))}
          </div>
        </Modal>
      )}

      {confirmSend && (
        <Modal title="Send quotation" onClose={() => setConfirmSend(null)}>
          <div className="stack">
            <dl className="kv">
              <dt>Machine</dt><dd>{confirmSend.machine}</dd>
              <dt>Buyer segment</dt><dd><SegBadge seg={confirmSend.segment} /></dd>
              <dt>Recipients</dt><dd><b>{confirmSend.count}</b> buyer(s) who enquired for this machine</dd>
            </dl>
            {confirmSend.count ? (
              <div className="table-wrap" style={{ maxHeight: 220, overflow: 'auto' }}>
                <table>
                  <thead><tr><th>Buyer</th><th>Segment</th><th>Channel</th><th>To</th></tr></thead>
                  <tbody>
                    {confirmSend.buyers.map((b, i) => (
                      <tr key={i}>
                        <td className="t-main">{b.name}</td>
                        <td><SegBadge seg={b.segment} /></td>
                        <td><span className="badge b-chan">{b.channel}</span></td>
                        <td className="t-sub">{b.channel === 'whatsapp' ? (b.phone || '—') : b.email}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted" style={{ margin: 0 }}>
                No buyers in the <b>{confirmSend.segment}</b> segment enquired for <b>{confirmSend.machine}</b>.
                Change the Buyer segment on the row, or add a matching buyer enquiry.
              </p>
            )}
            <div className="modal-foot">
              <button className="btn btn-outline" onClick={() => setConfirmSend(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={!confirmSend.count || busy?.startsWith('send-')} onClick={doSend}>
                ➤ Send to {confirmSend.count} buyer(s)
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}


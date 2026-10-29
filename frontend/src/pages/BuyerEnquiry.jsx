import { useEffect, useState } from 'react'
import { api } from '../api/index.js'
import { useStore } from '../store/useStore.jsx'
import { fmtDate, DateFilter, Modal, SegBadge } from '../components/ui.jsx'

const PAGE_SIZE = 25
const PRIORITIES = ['Very high', 'High', 'Medium', 'Low']
const STATUSES = ['New', 'Junior List', 'Junior Hot List', 'Head Very Hot List', 'MD Pending Call List', 'Potential Deal List']
const BLANK = {
  company: '', city: '', make: '', model: '', priority: 'High', status: 'New',
  name: '', email: '', phone: '', quantity: 1, channel: 'whatsapp', segment: 'hot',
}

export default function BuyerEnquiry() {
  const { flash } = useStore()
  const [data, setData] = useState({ rows: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [channel, setChannel] = useState('')
  const [q, setQ] = useState('')
  const [range, setRange] = useState(null)
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [add, setAdd] = useState(null)
  const [makes, setMakes] = useState([])
  const [models, setModels] = useState([])

  useEffect(() => {
    setLoading(true)
    api.enquiries({
      channel, q, page, pageSize: PAGE_SIZE,
      from: range?.fromDate, to: range?.toDate,
    }).then((d) => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [channel, q, range, page, reload])

  // Make / Model options for the Add form (active masters only).
  useEffect(() => {
    api.machineMakes().then((d) => setMakes((d.rows || []).filter((r) => r.active))).catch(() => {})
    api.models().then((d) => setModels((d.rows || []).filter((r) => r.active))).catch(() => {})
  }, [])

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  const submit = async () => {
    if (!add.company?.trim() || !add.model?.trim()) { flash('Company name and model are required', 'err'); return }
    await api.createEnquiry(add)
    setAdd(null)
    flash('Buyer enquiry added')
    setPage(1); setReload((r) => r + 1)
  }

  return (
    <div className="stack">
      <div className="page-actions">
        <div className="toolbar">
          <input className="search-input" placeholder="🔍 Search ref / machine / buyer…"
            value={q} onChange={(e) => { setPage(1); setQ(e.target.value) }} />
          <select className="filter-select" value={channel} onChange={(e) => { setPage(1); setChannel(e.target.value) }}>
            <option value="">All channels</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="email">Email</option>
          </select>
          <button className="btn btn-primary" onClick={() => setAdd({ ...BLANK })}>＋ Add Enquiry</button>
        </div>
        <DateFilter onFilter={(r) => { setPage(1); setRange(r) }} onReset={() => { setPage(1); setRange(null) }} />
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>S.No</th><th>Enq No</th><th>Enq Date</th><th>Company Name</th><th>Buyer</th><th>City</th><th>Make</th><th>Model</th><th>Priority</th><th>Segment</th></tr>
            </thead>
            <tbody>
              {data.rows.map((e, i) => (
                <tr key={e.id}>
                  <td className="t-sub">{(page - 1) * PAGE_SIZE + i + 1}</td>
                  <td className="t-main">{e.ref}</td>
                  <td className="t-sub">{fmtDate(e.received_at)}</td>
                  <td>{e.buyer_company || '—'}</td>
                  <td>{e.buyer_name || '—'}</td>
                  <td>{e.buyer_city || '—'}</td>
                  <td>{e.make || '—'}</td>
                  <td>{e.model || e.machine || '—'}</td>
                  <td>{e.priority ? <span className="badge b-chan">{e.priority}</span> : '—'}</td>
                  <td>{e.segment ? <SegBadge seg={e.segment} /> : '—'}</td>
                </tr>
              ))}
              {!loading && !data.rows.length && <tr><td colSpan="10" className="muted" style={{ textAlign: 'center', padding: 30 }}>No enquiries yet — click “Add Enquiry”.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="pager">
          <span className="t-sub">Page {page} of {pages}</span>
          <div className="toolbar">
            <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage(1)}>« First</button>
            <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
            <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next ›</button>
            <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => setPage(pages)}>Last »</button>
          </div>
        </div>
      </div>

      {add && (
        <Modal title="Add Buyer Enquiry" onClose={() => setAdd(null)}>
          <div className="form-grid">
            <div className="row-2">
              <div className="field"><label>Company Name *</label><input value={add.company} onChange={(e) => setAdd({ ...add, company: e.target.value })} placeholder="e.g. Murugan Spinners" /></div>
              <div className="field"><label>City</label><input value={add.city} onChange={(e) => setAdd({ ...add, city: e.target.value })} placeholder="Coimbatore" /></div>
            </div>
            <div className="row-2">
              <div className="field"><label>Make</label>
                <select value={add.make} onChange={(e) => setAdd({ ...add, make: e.target.value })}>
                  <option value="">-- Select --</option>
                  {makes.map((m) => <option key={m.id} value={m.name}>{m.name}{m.category ? ` (${m.category})` : ''}</option>)}
                </select></div>
              <div className="field"><label>Model *</label>
                <select value={add.model} onChange={(e) => setAdd({ ...add, model: e.target.value })}>
                  <option value="">-- Select --</option>
                  {models.map((m) => <option key={m.id} value={m.name}>{m.name}</option>)}
                </select></div>
            </div>
            <div className="row-2">
              <div className="field"><label>Priority</label>
                <select value={add.priority} onChange={(e) => setAdd({ ...add, priority: e.target.value })}>
                  {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select></div>
              <div className="field"><label>Status</label>
                <select value={add.status} onChange={(e) => setAdd({ ...add, status: e.target.value })}>
                  {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select></div>
            </div>
            <div className="row-2">
              <div className="field"><label>Contact Name</label><input value={add.name} onChange={(e) => setAdd({ ...add, name: e.target.value })} placeholder="Contact person" /></div>
              <div className="field"><label>Email</label><input value={add.email} onChange={(e) => setAdd({ ...add, email: e.target.value })} placeholder="buyer@example.com" /></div>
            </div>
            <div className="row-2">
              <div className="field"><label>Phone</label><input value={add.phone} onChange={(e) => setAdd({ ...add, phone: e.target.value })} placeholder="+91…" /></div>
              <div className="field"><label>Quantity</label><input type="number" min="1" value={add.quantity} onChange={(e) => setAdd({ ...add, quantity: e.target.value })} /></div>
            </div>
            <div className="row-2">
              <div className="field"><label>Channel</label>
                <select value={add.channel} onChange={(e) => setAdd({ ...add, channel: e.target.value })}>
                  <option value="email">Email</option><option value="whatsapp">WhatsApp</option>
                </select></div>
              <div className="field"><label>Segment</label>
                <select value={add.segment} onChange={(e) => setAdd({ ...add, segment: e.target.value })}>
                  <option value="cold">Cold</option><option value="hot">Hot</option><option value="very_hot">Very Hot</option>
                </select></div>
            </div>
            <div className="modal-foot">
              <button className="btn btn-outline" onClick={() => setAdd(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={submit}>Add enquiry</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from '../api/index.js'
import { money, fmtDate, DateFilter, Modal, Empty } from '../components/ui.jsx'

const PAGE_SIZE = 25
const FREQ = [
  { v: 'daily', label: 'Daily' },
  { v: 'weekly', label: 'Weekly' },
  { v: 'dnd', label: "Don't disturb" },
]

function ViewModal({ id, onClose }) {
  const [row, setRow] = useState(null)
  useEffect(() => { api.quotation(id).then((d) => setRow(d.row)) }, [id])
  return (
    <Modal title="Quotation sent" onClose={onClose}>
      {!row ? <div className="muted">Loading…</div> : (
        <div className="stack">
          <dl className="kv">
            <dt>Ref</dt><dd>{row.ref}</dd>
            <dt>Buyer</dt><dd>{row.buyer_name} · {row.buyer_company}</dd>
            <dt>Machine</dt><dd>{row.machine}</dd>
            <dt>Quantity</dt><dd>{row.qty}</dd>
            <dt>Amount</dt><dd className="money" style={{ color: 'var(--brand-700)' }}>{money(row.amount)} / unit</dd>
            <dt>Channel</dt><dd><span className="badge b-chan">{row.channel}</span></dd>
            <dt>Sent</dt><dd>{fmtDate(row.sent_at)}</dd>
          </dl>
          <div className="field">
            <label>Message delivered to buyer ({row.channel} template)</label>
            {row.channel === 'whatsapp' ? (
              <div className="wa-preview"><div className="wa-bubble" style={{ whiteSpace: 'pre-wrap' }}>
                {row.rendered_body || `Hello ${row.buyer_name}, our offer for ${row.machine}: ${money(row.amount)}.`}
              </div></div>
            ) : (
              <div className="email-preview">
                {row.rendered_subject ? <div className="email-subject">Subject: {row.rendered_subject}</div> : null}
                <div className="email-body" style={{ whiteSpace: 'pre-wrap' }}>
                  {row.rendered_body || `Hello ${row.buyer_name}, our offer for ${row.machine}: ${money(row.amount)}.`}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}

function ChatModal({ id, buyer, onClose }) {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.chat(id).then((d) => setRows(d.rows)) }, [id])
  return (
    <Modal title={`Chat history — ${buyer}`} onClose={onClose}>
      {!rows ? <div className="muted">Loading…</div> : !rows.length ? <Empty icon="💬" title="No messages yet" /> : (
        <div className="chatlog">
          {rows.map((m, i) => (
            <div key={i} className={`chat-row ${m.direction === 'out' ? 'out' : 'in'}`}>
              <div className={`chat-bubble ${m.channel === 'whatsapp' ? 'wa' : 'em'} ${m.direction}`}>
                <div style={{ whiteSpace: 'pre-wrap' }}>{m.body}</div>
                <div className="chat-meta">{m.channel} · {m.direction === 'out' ? 'sent' : 'received'} · {fmtDate(m.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}

export default function BuyerQuotation() {
  const [data, setData] = useState({ rows: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [range, setRange] = useState(null)
  const [page, setPage] = useState(1)
  const [view, setView] = useState(null)
  const [chat, setChat] = useState(null)

  const load = () => {
    setLoading(true)
    api.quotations({ q, page, pageSize: PAGE_SIZE, from: range?.fromDate, to: range?.toDate })
      .then((d) => { setData(d); setLoading(false) })
  }
  useEffect(load, [q, range, page])

  const setFollowup = async (id, frequency) => {
    await api.setFollowup(id, frequency)
    setData((d) => ({ ...d, rows: d.rows.map((r) => (r.id === id ? { ...r, followup: frequency } : r)) }))
  }

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <div className="stack">
      <div className="page-actions">
        <div className="toolbar">
          <input className="search-input" placeholder="🔍 Search buyer / machine / ref…" value={q} onChange={(e) => { setPage(1); setQ(e.target.value) }} />
        </div>
        <DateFilter onFilter={(r) => { setPage(1); setRange(r) }} onReset={() => { setPage(1); setRange(null) }} />
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Buyer Quotations</h3>
          <span className="hint">{data.total.toLocaleString('en-IN')} sent{loading ? ' · loading…' : ''}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Date</th><th>Buyer</th><th>Machine</th><th>Amount</th><th>Channel</th><th>Quotation</th><th>Follow-up</th><th>Chat</th></tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.id}>
                  <td className="t-sub">{fmtDate(r.sent_at)}</td>
                  <td className="t-main">{r.buyer_name}<div className="t-sub">{r.buyer_company}</div></td>
                  <td>{r.machine}</td>
                  <td className="money">{money(r.amount)}</td>
                  <td><span className="badge b-chan">{r.channel}</span></td>
                  <td><button className="btn btn-outline btn-sm" onClick={() => setView(r.id)}>👁 View</button></td>
                  <td>
                    <select className="cell-input" value={r.followup || ''} onChange={(e) => setFollowup(r.id, e.target.value)}>
                      <option value="" disabled>Set…</option>
                      {FREQ.map((f) => <option key={f.v} value={f.v}>{f.label}</option>)}
                    </select>
                  </td>
                  <td><button className="btn btn-outline btn-sm" onClick={() => setChat({ id: r.id, buyer: r.buyer_name })}>💬 History</button></td>
                </tr>
              ))}
              {!loading && !data.rows.length && (
                <tr><td colSpan="8"><Empty icon="💹" title="No quotations yet" sub="Send a proposal from the Supplier Proposal screen to create buyer quotations." /></td></tr>
              )}
            </tbody>
          </table>
        </div>
        {data.total > PAGE_SIZE && (
          <div className="pager">
            <span className="t-sub">Page {page} of {pages}</span>
            <div className="toolbar">
              <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
              <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next ›</button>
            </div>
          </div>
        )}
      </div>

      {view && <ViewModal id={view} onClose={() => setView(null)} />}
      {chat && <ChatModal id={chat.id} buyer={chat.buyer} onClose={() => setChat(null)} />}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api } from '../api/index.js'
import { money, fmtDate, DateFilter, Modal, Empty } from '../components/ui.jsx'

const PAGE_SIZE = 50
// Tabs follow the buyer's WhatsApp answer (Interested / Send photos / Not interested)
// plus anyone who wrote something a person needs to handle.
const TABS = [
  { v: 'all', label: 'All' },
  { v: 'potential', label: 'Potential' },
  { v: 'photos', label: 'Photos Requested' },
  { v: 'support', label: 'Need Support' },
  { v: 'not_interested', label: 'Not Interested' },
]
const STATUS = {
  sent: ['Awaiting reply', 'b-muted'],
  interested: ['Interested', 'b-ok'],
  photos_requested: ['Wants photos', 'b-pend'],
  photos_sent: ['Photos sent', 'b-sent'],
  not_interested: ['Not interested', 'b-reject'],
}

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

const CHAT_TABS = [{ v: 'whatsapp', label: 'WhatsApp' }, { v: 'email', label: 'Email' }]

function ChatModal({ id, buyer, onClose }) {
  const [chat, setChat] = useState(null)
  const [chTab, setChTab] = useState(null)   // 'whatsapp' | 'email' — the conversation shown & replied on
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [note, setNote] = useState(null)
  const load = () => api.chat(id).then((d) => {
    setChat(d)
    // Open on WhatsApp (where the conversation happens) unless there are only emails.
    const hasWa = (d.rows || []).some((m) => m.channel !== 'email')
    setChTab((cur) => cur || (hasWa ? 'whatsapp' : (d.rows?.length ? 'email' : (d.reply_channel || 'whatsapp'))))
  })
  useEffect(() => { load() }, [id])

  // Team reply to the buyer on the open tab's channel.
  const send = async (resolve) => {
    setSending(true); setNote(null)
    try {
      const r = await api.replyQuotation(id, text, resolve, chTab)
      setText('')
      setNote(r.window_closed
        ? { err: true, msg: "Sent, but this buyer hasn't messaged in 24h — WhatsApp may not deliver free text." }
        : { msg: `Sent on ${r.channel}${r.simulated ? ' (simulated)' : ''}${resolve ? ' · marked resolved' : ''}.` })
      load()
    } catch (err) {
      setNote({ err: true, msg: err.message || 'Reply failed' })
    } finally { setSending(false) }
  }

  const all = chat?.rows
  const rows = (all || []).filter((m) => (m.channel === 'email' ? 'email' : 'whatsapp') === chTab)
  const count = (v) => (all || []).filter((m) => (m.channel === 'email' ? 'email' : 'whatsapp') === v).length
  const to = chat?.channels?.[chTab]
  return (
    <Modal title={`Chat history — ${buyer}`} onClose={onClose} wide>
      {!all ? <div className="muted">Loading…</div> : (
        <>
          <div className="tabs" style={{ marginBottom: 10 }}>
            {CHAT_TABS.map((t) => (
              <button key={t.v} className={`tab${chTab === t.v ? ' active' : ''}`} onClick={() => { setChTab(t.v); setNote(null) }}>
                {t.label}<span className="badge b-muted" style={{ marginLeft: 6, padding: '1px 7px' }}>{count(t.v)}</span>
              </button>
            ))}
          </div>
          {!rows.length ? <Empty icon="💬" title={`No ${chTab === 'email' ? 'email' : 'WhatsApp'} messages yet`} /> : (
            <div className="chatlog chatlog-tall">
              {rows.map((m, i) => (
                <div key={i} className={`chat-row ${m.direction === 'out' ? 'out' : 'in'}`}>
                  <div className={`chat-bubble ${m.channel === 'whatsapp' ? 'wa' : 'em'} ${m.direction}`}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{m.body}</div>
                    <div className="chat-meta">{m.direction === 'out' ? 'sent' : 'received'} · {fmtDate(m.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      {chat && (to ? (
        <div className="stack" style={{ marginTop: 12 }}>
          <div className="field">
            <label>Reply to {buyer} on {chTab === 'email' ? `email (${to})` : `WhatsApp (${to})`}</label>
            <textarea style={{ minHeight: 70 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your reply…" />
          </div>
          {chTab === 'whatsapp' && chat.window_open === false && (
            <div className="t-sub" style={{ color: 'var(--warn-600)' }}>
              This buyer hasn't messaged in the last 24 hours, so WhatsApp may not deliver a typed reply.
            </div>
          )}
          {note && <div className="t-sub" style={{ color: note.err ? 'var(--danger-600)' : 'var(--ok-600)' }}>{note.msg}</div>}
          <div className="modal-foot" style={{ marginTop: 0 }}>
            {chat.support_open && (
              <button className="btn btn-outline" disabled={sending || !text.trim()} onClick={() => send(true)}>Send &amp; mark resolved</button>
            )}
            <button className="btn btn-primary" disabled={sending || !text.trim()} onClick={() => send(false)}>{sending ? 'Sending…' : '➤ Send'}</button>
          </div>
        </div>
      ) : (
        <div className="t-sub" style={{ marginTop: 12 }}>
          {buyer} has no {chTab === 'email' ? 'email address' : 'phone number'} on file, so you can't reply here.
        </div>
      ))}
    </Modal>
  )
}

/* Buyer quotations for one tab — table, pager, quotation view, chat (with reply) and
   Mark resolved. Used by the Buyer Quotation screen and by the Potential / Need Support
   tabs on Supplier Proposal. onLoaded gets { total, counts } after each load. */
export function QuotationList({ tab = 'all', q = '', range = null, proposal = '', onLoaded }) {
  const [data, setData] = useState({ rows: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [view, setView] = useState(null)
  const [chat, setChat] = useState(null)

  const load = () => {
    setLoading(true)
    api.quotations({ q, tab, proposal, page, pageSize: PAGE_SIZE, from: range?.fromDate, to: range?.toDate })
      .then((d) => { setData(d); setLoading(false); onLoaded?.(d) })
  }
  useEffect(() => { setPage(1) }, [q, range, tab, proposal])
  useEffect(load, [q, range, page, tab, proposal])

  const resolve = async (id) => {
    await api.resolveSupport(id)
    load()
  }

  const setFollowup = async (id, frequency) => {
    await api.setFollowup(id, frequency)
    setData((d) => ({ ...d, rows: d.rows.map((r) => (r.id === id ? { ...r, followup: frequency } : r)) }))
  }

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Date</th><th>Buyer</th><th>Company</th><th>Machine</th><th>Amount</th><th>Channel</th><th>Status</th><th>Quotation</th><th>Follow-up</th><th>Chat</th></tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.id}>
                <td className="t-sub">{fmtDate(r.sent_at)}</td>
                <td className="t-main">{r.buyer_name}</td>
                <td>{r.buyer_company || '—'}</td>
                <td>{r.machine}</td>
                <td className="money">{money(r.amount)}</td>
                <td>
                  {!!r.via_whatsapp && <span className="badge b-chan">whatsapp</span>}
                  {!!r.via_email && <span className="badge b-chan" style={{ marginLeft: r.via_whatsapp ? 4 : 0 }}>email</span>}
                  {!r.via_whatsapp && !r.via_email && <span className="badge b-chan">{r.channel}</span>}
                </td>
                <td style={{ maxWidth: 260 }}>
                  {(() => { const [label, cls] = STATUS[r.buyer_status] || STATUS.sent; return <span className={`badge ${cls}`}>{label}</span> })()}
                  {r.interested_at && r.buyer_status !== 'interested' && r.buyer_status !== 'not_interested' && (
                    <span className="badge b-ok" style={{ marginLeft: 4 }}>Interested</span>
                  )}
                  {!!r.support_open && (
                    <div style={{ marginTop: 6 }}>
                      <span className="badge b-reject">Need support</span>
                      <div className="t-sub" style={{ whiteSpace: 'normal', margin: '4px 0' }} title={r.support_reason}>“{r.support_reason}”</div>
                      <button className="btn btn-outline btn-sm" style={{ padding: '2px 8px', fontSize: 12 }} onClick={() => resolve(r.id)}>✓ Mark resolved</button>
                    </div>
                  )}
                </td>
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
              <tr><td colSpan="10">{tab === 'all'
                ? <Empty icon="💹" title="No quotations yet" sub="Send a proposal from the Supplier Proposal screen to create buyer quotations." />
                : <Empty icon="💬" title="No buyers here yet" sub="Buyers move into this tab automatically when they answer on WhatsApp." />}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <span className="t-sub">Page {page} of {pages} · {data.total} row(s)</span>
        <div className="toolbar">
          <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage(1)}>« First</button>
          <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
          <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next ›</button>
          <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => setPage(pages)}>Last »</button>
        </div>
      </div>

      {view && <ViewModal id={view} onClose={() => setView(null)} />}
      {chat && <ChatModal id={chat.id} buyer={chat.buyer} onClose={() => { setChat(null); load() }} />}
    </>
  )
}

/* Potential / Need Support pages (opened from the buttons on Supplier Proposal). */
export function BuyerTabPage({ tab }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const proposal = params.get('proposal') || ''
  const proNo = params.get('pro') || ''
  const [q, setQ] = useState('')
  const [range, setRange] = useState(null)
  return (
    <div className="stack">
      <div className="page-actions">
        <div className="toolbar">
          <button className="btn btn-outline btn-sm" onClick={() => navigate(proposal ? `/supplier-proposal/${proposal}` : '/supplier-proposal')}>
            ‹ {proposal ? `Pro No ${proNo || proposal}` : 'Supplier Proposal'}
          </button>
          {proposal && <button className="btn btn-outline btn-sm" onClick={() => navigate(tab === 'support' ? '/need-support' : '/potential')}>Show all proposals</button>}
          <input className="search-input" placeholder="🔍 Search buyer / machine / ref…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <DateFilter onFilter={setRange} onReset={() => setRange(null)} />
      </div>
      <div className="card">
        <QuotationList tab={tab} q={q} range={range} proposal={proposal} />
      </div>
    </div>
  )
}

export default function BuyerQuotation() {
  const [q, setQ] = useState('')
  const [range, setRange] = useState(null)
  const [info, setInfo] = useState({ counts: null })
  // The tab lives in the URL (?tab=potential) so other screens can link straight to it.
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'all'
  const setTab = (v) => setParams(v === 'all' ? {} : { tab: v })

  return (
    <div className="stack">
      <div className="page-actions">
        <div className="toolbar">
          <input className="search-input" placeholder="🔍 Search buyer / machine / ref…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <DateFilter onFilter={setRange} onReset={() => setRange(null)} />
      </div>

      <div className="card">
        <div className="card-pad" style={{ paddingBottom: 0 }}>
          <div className="tabs">
            {TABS.map((t) => (
              <button key={t.v} className={`tab${tab === t.v ? ' active' : ''}`} onClick={() => setTab(t.v)}>
                {t.label}
                {info.counts && t.v !== 'all' && info.counts[t.v] > 0 && (
                  <span className={`badge ${t.v === 'support' ? 'b-reject' : 'b-muted'}`} style={{ marginLeft: 6, padding: '1px 7px' }}>{info.counts[t.v]}</span>
                )}
              </button>
            ))}
          </div>
        </div>
        <QuotationList tab={tab} q={q} range={range} onLoaded={(d) => setInfo({ counts: d.counts })} />
      </div>
    </div>
  )
}

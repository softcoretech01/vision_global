import { useEffect, useState, Fragment } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/index.js'
import { useStore } from '../store/useStore.jsx'
import { Modal, fmtDate } from '../components/ui.jsx'

// Shared section list — also consumed by the sidebar to render the submenu.
export const ADMIN_SECTIONS = [
  { id: 'users', label: 'Users', ico: '👤' },
  { id: 'keywords', label: 'Keywords', ico: '🔑' },
  { id: 'machine_make', label: 'Machine Make', ico: '🏭' },
  { id: 'model', label: 'Model', ico: '🧩' },
  { id: 'machine', label: 'Machine', ico: '⚙️' },
  { id: 'enquiry', label: 'Buyer-Enquiry Channels', ico: '📥' },
  { id: 'proposal', label: 'Supplier-Proposal Channels', ico: '📤' },
  { id: 'templates', label: 'Templates', ico: '📝' },
  { id: 'integrations', label: 'Integrations', ico: '🔌' },
]

/* ---------------- Keywords ---------------- */
function Keywords() {
  const { flash } = useStore()
  const [rows, setRows] = useState([])
  const [word, setWord] = useState('')
  const load = () => api.keywords().then((d) => setRows(d.rows))
  useEffect(() => { load() }, [])
  const add = async () => { if (!word.trim()) return; await api.addKeyword(word.trim()); setWord(''); flash('Keyword added'); load() }
  const del = async (id) => { await api.deleteKeyword(id); flash('Keyword removed'); load() }
  return (
    <div className="card">
      <div className="card-pad">
        <div className="toolbar" style={{ marginBottom: 14 }}>
          <input className="search-input" placeholder="Add a keyword (e.g. CNC machine, quotation)…"
            value={word} onChange={(e) => setWord(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') add() }} />
          <button className="btn btn-primary" onClick={add}>＋ Add</button>
        </div>
        <div className="kw-chips">
          {rows.map((k) => (
            <span className="kw-chip" key={k.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {k.word}
              <button className="chip-x" onClick={() => del(k.id)} title="Remove">×</button>
            </span>
          ))}
          {!rows.length && <span className="muted">No keywords yet — add one above.</span>}
        </div>
      </div>
    </div>
  )
}

/* ---------------- Users ---------------- */
function Users() {
  const { flash } = useStore()
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(null)
  const load = () => api.users().then((d) => setRows(d.rows))
  useEffect(() => { load() }, [])

  const save = async () => {
    await api.saveUser(form.id, form)
    setForm(null); flash('User saved'); load()
  }
  return (
    <div className="card">
      <div className="card-actions">
        <button className="btn btn-primary btn-sm" onClick={() => setForm({ name: '', email: '', phone: '', role: 'operator', password: '' })}>＋ Add user</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Status</th><th>Created</th><th></th></tr></thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id}>
                <td className="t-main">{u.name}</td><td>{u.email}</td><td className="t-sub">{u.phone || '—'}</td>
                <td><span className="chip">{u.role}</span></td>
                <td><span className={`badge ${u.status === 'active' ? 'b-ok' : 'b-muted'}`}>{u.status}</span></td>
                <td className="t-sub">{fmtDate(u.created_at)}</td>
                <td className="right"><button className="btn btn-outline btn-sm" onClick={() => setForm({ ...u, password: '' })}>Edit</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {form && (
        <Modal title={form.id ? 'Edit user' : 'Add user'} onClose={() => setForm(null)}>
          <div className="form-grid">
            <div className="row-2">
              <div className="field"><label>Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="field"><label>Email</label><input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} disabled={!!form.id} /></div>
            </div>
            <div className="row-2">
              <div className="field"><label>Phone</label><input value={form.phone || ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
              <div className="field"><label>Role</label>
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="operator">Operator</option><option value="admin">Admin</option><option value="super_admin">Super Admin</option>
                </select>
              </div>
            </div>
            <div className="field"><label>{form.id ? 'New password (blank = keep)' : 'Password'}</label>
              <input type="password" value={form.password || ''} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
            {form.id && <div className="field"><label>Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="active">active</option><option value="disabled">disabled</option></select></div>}
            <div className="modal-foot">
              <button className="btn btn-outline" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={save}>Save</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

/* ---------------- Channels (enquiry / proposal) ---------------- */
function Channels({ purpose, title }) {
  const { flash } = useStore()
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(null)
  const load = () => api.channels(purpose).then((d) => setRows(d.rows))
  useEffect(() => { load() }, [purpose])

  const save = async () => { await api.saveChannel({ ...form, purpose }); setForm(null); flash('Channel saved'); load() }
  const del = async (id) => { await api.deleteChannel(id); flash('Channel removed'); load() }

  return (
    <div className="card">
      <div className="card-actions">
        <button className="btn btn-primary btn-sm" onClick={() => setForm({ type: 'email', label: '', address: '', active: 1 })}>＋ Add channel</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Type</th><th>Label</th><th>Address / Number</th><th>Active</th><th></th></tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td><span className="badge b-chan">{c.type}</span></td>
                <td className="t-main">{c.label}</td><td>{c.address}</td>
                <td><span className={`badge ${c.active ? 'b-ok' : 'b-muted'}`}>{c.active ? 'yes' : 'no'}</span></td>
                <td className="right"><div className="flex" style={{ justifyContent: 'flex-end' }}>
                  <button className="btn btn-outline btn-sm" onClick={() => setForm(c)}>Edit</button>
                  <button className="btn btn-danger btn-sm" onClick={() => del(c.id)}>Delete</button>
                </div></td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="5" className="muted" style={{ textAlign: 'center', padding: 24 }}>No channels configured.</td></tr>}
          </tbody>
        </table>
      </div>
      {form && (
        <Modal title={form.id ? 'Edit channel' : 'Add channel'} onClose={() => setForm(null)}>
          <div className="form-grid">
            <div className="field"><label>Type</label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}><option value="email">Email</option></select></div>
            <div className="field"><label>Label</label><input value={form.label || ''} onChange={(e) => setForm({ ...form, label: e.target.value })} /></div>
            <div className="field"><label>{form.type === 'whatsapp' ? 'WhatsApp number' : 'Email address'}</label>
              <input value={form.address || ''} onChange={(e) => setForm({ ...form, address: e.target.value })} /></div>
            <label className="flex"><input type="checkbox" checked={!!form.active} onChange={(e) => setForm({ ...form, active: e.target.checked ? 1 : 0 })} /> Active</label>
            <div className="modal-foot"><button className="btn btn-outline" onClick={() => setForm(null)}>Cancel</button><button className="btn btn-primary" onClick={save}>Save</button></div>
          </div>
        </Modal>
      )}
    </div>
  )
}

/* ---------------- Templates ---------------- */
/* Every message the app sends, grouped as on the page. Bot replies go out inside the
   buyer's 24-hour WhatsApp window, so they never need an approved Meta template. */
const TEMPLATE_GROUPS = [
  { title: 'Buyer messages', kinds: [
    ['buyer_quotation', 'Buyer Quotation'], ['quotation_prompt', 'Quotation Prompt'], ['followup', 'Follow-up'],
  ] },
  { title: 'WhatsApp bot replies to buyers', reply: true, kinds: [
    ['interested_reply', 'Interested'], ['photos_reply', 'Send Photos'], ['photos_sent_reply', 'Photos Sent'],
    ['not_interested_reply', 'Not Interested'], ['thanks_reply', 'Thanks / Ok'], ['greeting_pending_reply', 'Hello (pending)'],
    ['greeting_interested_reply', 'Hello (interested)'], ['greeting_reply', 'Hello'], ['bye_reply', 'Bye'],
    ['support_reply', 'Need Support'], ['price_reply', 'Price'], ['photos_wait_reply', 'Photos Again'],
    ['visit_reply', 'Location'], ['delivery_reply', 'Delivery'], ['payment_reply', 'Payment'],
    ['details_reply', 'Details'], ['generic_reply', 'Other Question'], ['noted_reply', 'More Messages'],
  ] },
  { title: 'Supplier messages', kinds: [
    ['photo_request', 'Photo Request'], ['details_request', 'Details Request'], ['details_followup', 'Details Follow-up'],
  ] },
  { title: 'Other', kinds: [['whatsapp_response', 'WhatsApp Response']] },
]
const KIND = Object.fromEntries(TEMPLATE_GROUPS.flatMap((g) => g.kinds))
const REPLY_KINDS = new Set(['quotation_prompt', ...TEMPLATE_GROUPS.filter((g) => g.reply).flatMap((g) => g.kinds.map(([k]) => k))])
const preview = (t) => (t.subject || (t.body || '').split('\n').find((l) => l.trim()) || '—')

function Templates() {
  const { flash } = useStore()
  const [rows, setRows] = useState([])
  const [edit, setEdit] = useState(null)
  const [adding, setAdding] = useState(null)
  const load = () => api.templates().then((d) => setRows(d.rows))
  useEffect(() => { load() }, [])
  const save = async () => { await api.saveTemplate(edit.id, edit); setEdit(null); flash('Template saved'); load() }
  const create = async () => { await api.createTemplate(adding); setAdding(null); flash('Template added'); load() }
  // Rows in page order: by group, then by the kind order inside it; unknown kinds last.
  const order = TEMPLATE_GROUPS.flatMap((g) => g.kinds.map(([k]) => k))
  const groups = TEMPLATE_GROUPS.map((g) => ({
    ...g, rows: rows.filter((t) => g.kinds.some(([k]) => k === t.kind)).sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind)),
  }))
  const other = rows.filter((t) => !order.includes(t.kind))
  if (other.length) groups.push({ title: 'Other', rows: other })
  const metaCell = (t) => {
    if (t.channel === 'email') return '—'
    if (REPLY_KINDS.has(t.kind)) return <span className="t-sub">not needed</span>
    return t.wa_template ? <code>{t.wa_template}</code> : <span className="badge b-muted">not set</span>
  }
  const fields = (t, set) => (
    <>
      <div className="field"><label>Name</label><input value={t.name} onChange={(e) => set({ ...t, name: e.target.value })} /></div>
      {t.channel !== 'whatsapp' && (
        <div className="field"><label>Subject (email)</label><input value={t.subject || ''} onChange={(e) => set({ ...t, subject: e.target.value })} /></div>
      )}
      <div className="field"><label>Message</label><textarea style={{ minHeight: 140 }} value={t.body} onChange={(e) => set({ ...t, body: e.target.value })} /></div>
      {t.channel !== 'email' && !REPLY_KINDS.has(t.kind) && <WaTemplateFields t={t} set={set} />}
    </>
  )
  return (
    <div className="card">
      <div className="card-actions">
        <div><span className="hint">placeholders: {'{{buyer}}'} {'{{company}}'} {'{{city}}'} {'{{machine}}'} {'{{model}}'} {'{{details}}'} {'{{qty}}'} {'{{price}}'} {'{{total}}'} {'{{quotation_no}}'} {'{{pro_no}}'} {'{{date}}'} {'{{ref}}'} {'{{supplier}}'} · supplier details: {'{{missing}}'}</span></div>
        <button className="btn btn-primary btn-sm" onClick={() => setAdding({ kind: 'buyer_quotation', channel: 'any', name: '', subject: '', body: '' })}>＋ Add template</button>
      </div>
      <div className="table-wrap">
        <table className="wrap">
          <thead><tr><th>Kind</th><th>Name</th><th>Channel</th><th>Subject / message</th><th>Meta template</th><th></th></tr></thead>
          <tbody>
            {groups.filter((g) => g.rows.length).map((g) => (
              <Fragment key={g.title}>
                <tr><td colSpan="6" className="t-main" style={{ background: 'var(--brand-050)', fontWeight: 700 }}>{g.title}</td></tr>
                {g.rows.map((t) => (
                  <tr key={t.id}>
                    <td><span className="chip">{KIND[t.kind] || t.kind}</span></td>
                    <td className="t-main">{t.name}</td><td>{t.channel}</td>
                    <td className="t-sub" style={{ maxWidth: 380, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={t.body}>{preview(t)}</td>
                    <td className="t-sub">{metaCell(t)}</td>
                    <td className="right"><button className="btn btn-outline btn-sm" onClick={() => setEdit(t)}>Edit</button></td>
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <Modal title={`Edit — ${KIND[edit.kind] || edit.kind}`} onClose={() => setEdit(null)}>
          <div className="form-grid">
            {fields(edit, setEdit)}
            <div className="modal-foot"><button className="btn btn-outline" onClick={() => setEdit(null)}>Cancel</button><button className="btn btn-primary" onClick={save}>Save</button></div>
          </div>
        </Modal>
      )}
      {adding && (
        <Modal title="Add template" onClose={() => setAdding(null)}>
          <div className="form-grid">
            <div className="row-2">
              <div className="field"><label>Kind</label>
                <select value={adding.kind} onChange={(e) => setAdding({ ...adding, kind: e.target.value })}>
                  {TEMPLATE_GROUPS.map((g) => (
                    <optgroup key={g.title} label={g.title}>
                      {g.kinds.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                    </optgroup>
                  ))}
                </select></div>
              <div className="field"><label>Channel</label>
                <select value={adding.channel} onChange={(e) => setAdding({ ...adding, channel: e.target.value })}>
                  <option value="any">Any</option><option value="email">Email</option><option value="whatsapp">WhatsApp</option>
                </select></div>
            </div>
            {fields(adding, setAdding)}
            <div className="modal-foot"><button className="btn btn-outline" onClick={() => setAdding(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={!adding.name || !adding.body} onClick={create}>Add template</button></div>
          </div>
        </Modal>
      )}
    </div>
  )
}

/* Approved Meta template used when the recipient hasn't messaged in the last 24h. */
function WaTemplateFields({ t, set }) {
  const params = [...new Set([...(t.body || '').matchAll(/\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}/g)].map((m) => m[1]))]
  return (
    <>
      <div className="row-2">
        <div className="field"><label>Meta template name (WhatsApp)</label>
          <input placeholder="e.g. buyer_quotation" value={t.wa_template || ''} onChange={(e) => set({ ...t, wa_template: e.target.value })} /></div>
        <div className="field"><label>Template language</label>
          <input placeholder="en" value={t.wa_lang || ''} onChange={(e) => set({ ...t, wa_lang: e.target.value })} /></div>
      </div>
      <div className="t-sub">
        WhatsApp only delivers free text to people who messaged you in the last 24 hours. For anyone else this approved
        Meta template is sent instead. Create it in WhatsApp Manager with the same body and <b>named</b> variables
        {params.length ? <>: {params.map((p) => <code key={p} style={{ marginRight: 4 }}>{`{{${p}}}`}</code>)}</> : '.'}
      </div>
    </>
  )
}

/* ---------------- Integrations ---------------- */
function Integrations() {
  const { flash } = useStore()
  const [info, setInfo] = useState(null)
  const [testing, setTesting] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [result, setResult] = useState(null)
  useEffect(() => { api.integrations().then(setInfo) }, [])
  const test = async () => {
    setTesting(true)
    const r = await api.testEmail()
    setResult(r); setTesting(false)
    flash(r.ok ? 'Email login OK (send + fetch)' : 'Email login failed', r.ok ? 'ok' : 'err')
  }
  const fetchNow = async () => {
    setFetching(true)
    try {
      const r = await api.fetchEmails()
      flash(r.detail || `Fetched ${r.fetched} new email(s) from ${r.matched} matched`, r.fetched ? 'ok' : 'err')
    } catch (err) { flash(err.message || 'Fetch failed', 'err') } finally { setFetching(false) }
  }
  if (!info) return <div className="card card-pad muted">Loading…</div>
  const e = info.email
  const w = info.whatsapp
  const copy = (txt) => { try { navigator.clipboard.writeText(txt); flash('Copied', 'ok') } catch { /* ignore */ } }
  return (
    <div className="stack">
      <div className="card">
        <div className="card-head"><h3>✉️ Supplier-Proposal Email</h3>
          <span className={`badge ${e.configured ? 'b-ok' : 'b-muted'}`}>{e.configured ? 'Connected' : 'Not connected'}</span></div>
        <div className="card-pad">
          <dl className="kv">
            <dt>Account</dt><dd>{e.account || '—'}</dd>
            <dt>Sending (SMTP)</dt><dd>{e.smtp_host || '—'} · <span className={`badge ${e.send_ready ? 'b-ok' : 'b-muted'}`}>{e.send_ready ? 'ready' : 'off'}</span></dd>
            <dt>Fetching (IMAP)</dt><dd>{e.imap_host || '—'} · <span className={`badge ${e.fetch_ready ? 'b-ok' : 'b-muted'}`}>{e.fetch_ready ? 'ready' : 'off'}</span></dd>
            <dt>Auto-fetch</dt><dd>{e.auto_fetch ? <span className="badge b-ok">every {Math.max(1, Math.round((e.fetch_interval || 180) / 60))} min</span> : <span className="badge b-muted">off (manual)</span>}</dd>
          </dl>
          <div className="flex" style={{ marginTop: 14, flexWrap: 'wrap' }}>
            <button className="btn btn-primary btn-sm" disabled={testing} onClick={test}>{testing ? 'Testing…' : '✓ Test login'}</button>
            <button className="btn btn-teal btn-sm" disabled={fetching} onClick={fetchNow}>{fetching ? 'Fetching…' : '📩 Fetch emails now'}</button>
            {result && <span className={`badge ${result.ok ? 'b-ok' : 'b-reject'}`} style={{ whiteSpace: 'normal', maxWidth: 640 }}>{result.detail}</span>}
          </div>
          <div className="t-sub" style={{ marginTop: 12 }}>
            Supplier emails matching your <b>Keywords</b> are fetched from this inbox into the Supplier Proposal screen.
            Configured in <code>backend/.env</code> (SMTP_* to send, IMAP_* to fetch) with a Gmail App Password.
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h3>💬 WhatsApp (Meta Cloud API)</h3>
          <span className={`badge ${w.configured ? 'b-ok' : 'b-muted'}`}>{w.configured ? 'Connected' : 'Not connected'}</span></div>
        <div className="card-pad">
          <dl className="kv">
            <dt>Business number</dt><dd>{w.number || '—'}</dd>
            <dt>Provider</dt><dd>{w.provider} · API {w.api_version}</dd>
            <dt>Sending</dt><dd><span className={`badge ${w.send_ready ? 'b-ok' : 'b-muted'}`}>{w.send_ready ? 'ready' : 'off'}</span></dd>
            <dt>Phone Number ID</dt><dd><span className={`badge ${w.phone_id_set ? 'b-ok' : 'b-reject'}`}>{w.phone_id_set ? 'set' : 'missing'}</span></dd>
            <dt>Access token</dt><dd><span className={`badge ${w.token_set ? 'b-ok' : 'b-reject'}`}>{w.token_set ? 'set' : 'missing'}</span></dd>
            <dt>Templates (24h+)</dt><dd>
              {(w.templates || []).length === 0 ? '—' : (w.templates || []).map((t) => (
                <div key={t.name} style={{ marginBottom: 4 }}>{t.name} → {t.wa_template
                  ? <>
                      <span className={`badge ${t.meta?.found === false || (t.meta?.status && t.meta.status !== 'APPROVED') ? 'b-reject' : 'b-ok'}`}>{t.wa_template} · {t.wa_lang || 'en'}</span>
                      {t.meta?.found === false && <span className="t-sub"> not found in Meta (check name/language)</span>}
                      {t.meta?.found && (
                        <span className="t-sub"> {t.meta.status}
                          {t.meta.header === 'IMAGE' && ' · photo header'}
                          {t.meta.buttons?.length ? ` · buttons: ${t.meta.buttons.join(' / ')}` : ''}
                          {t.meta.header === 'IMAGE' && !w.fallback_image && ' · rows without photos need WA_FALLBACK_IMAGE'}
                        </span>
                      )}
                    </>
                  : <span className="badge b-reject">no Meta template</span>}</div>
              ))}
            </dd>
          </dl>
          <div className="field" style={{ marginTop: 10 }}>
            <label>Webhook callback URL (set this in the Meta app dashboard)</label>
            <div className="flex" style={{ gap: 8 }}>
              <input className="cell-input" readOnly value={w.webhook_url} style={{ flex: 1, minWidth: 0 }} />
              <button className="btn btn-outline btn-sm" onClick={() => copy(w.webhook_url)}>Copy</button>
            </div>
          </div>
          <div className="field" style={{ marginTop: 8 }}>
            <label>Verify token</label>
            <div className="flex" style={{ gap: 8 }}>
              <input className="cell-input" readOnly value={w.verify_token} style={{ flex: 1, minWidth: 0 }} />
              <button className="btn btn-outline btn-sm" onClick={() => copy(w.verify_token)}>Copy</button>
            </div>
          </div>
          <div className="t-sub" style={{ marginTop: 12 }}>
            Quotations and follow-ups go out over WhatsApp for buyers whose channel is <b>WhatsApp</b>.
            Incoming supplier quotes and buyer replies arrive via the webhook above — Meta needs a <b>public HTTPS URL</b>,
            so on localhost run a tunnel (e.g. <code>ngrok http 8000</code>) and set <code>PUBLIC_BASE</code> in <code>backend/.env</code>.
            Add <code>WA_PHONE_ID</code> and <code>WA_TOKEN</code> (from Meta) to <code>backend/.env</code> to go live.
          </div>
        </div>
      </div>
    </div>
  )
}

/* ---------------- Machine masters (Make / Model / Machine) ----------------
   Reference lists used to recognize machines in supplier email & WhatsApp intake. */
function MasterList({ title, loader, saver, hasCategory }) {
  const { flash } = useStore()
  const [rows, setRows] = useState([])
  const [q, setQ] = useState('')
  const [form, setForm] = useState(null)
  const load = () => loader().then((d) => setRows(d.rows || []))
  useEffect(() => { load() }, [])
  const save = async () => {
    if (!form.name?.trim()) { flash('Name is required', 'err'); return }
    const r = await saver(form)
    if (r && r.ok === false) { flash(r.error || 'Could not save', 'err'); return }
    setForm(null); flash('Saved'); load()
  }
  const toggle = async (row) => { await saver({ ...row, active: row.active ? 0 : 1 }); load() }
  const ql = q.trim().toLowerCase()
  const shown = rows.filter((r) => !ql || r.name.toLowerCase().includes(ql) || (r.category || '').toLowerCase().includes(ql))
  const activeCount = rows.filter((r) => r.active).length
  return (
    <div className="card">
      <div className="card-actions">
        <span className="hint">{rows.length} total · {activeCount} active</span>
        <button className="btn btn-primary btn-sm" onClick={() => setForm(hasCategory ? { name: '', category: '', active: 1 } : { name: '', active: 1 })}>＋ Add</button>
      </div>
      <div className="card-pad" style={{ paddingBottom: 0 }}>
        <input className="search-input" placeholder="🔍 Search…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Name</th>{hasCategory && <th>Category</th>}<th>Status</th><th></th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td className="t-main">{r.name}</td>
                {hasCategory && <td>{r.category || '—'}</td>}
                <td><button className={`badge ${r.active ? 'b-ok' : 'b-muted'}`} style={{ cursor: 'pointer', border: 'none' }} onClick={() => toggle(r)} title="Toggle active">{r.active ? '✓ active' : 'inactive'}</button></td>
                <td className="right"><button className="btn btn-outline btn-sm" onClick={() => setForm(r)}>Edit</button></td>
              </tr>
            ))}
            {!shown.length && <tr><td colSpan={hasCategory ? 4 : 3} className="muted" style={{ textAlign: 'center', padding: 24 }}>No entries.</td></tr>}
          </tbody>
        </table>
      </div>
      {form && (
        <Modal title={form.id ? `Edit ${title}` : `Add ${title}`} onClose={() => setForm(null)}>
          <div className="form-grid">
            <div className="field"><label>Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            {hasCategory && <div className="field"><label>Category</label><input value={form.category || ''} onChange={(e) => setForm({ ...form, category: e.target.value })} /></div>}
            <label className="flex"><input type="checkbox" checked={!!form.active} onChange={(e) => setForm({ ...form, active: e.target.checked ? 1 : 0 })} /> Active</label>
            <div className="modal-foot"><button className="btn btn-outline" onClick={() => setForm(null)}>Cancel</button><button className="btn btn-primary" onClick={save}>Save</button></div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default function Administration() {
  const { section } = useParams()
  const tab = ADMIN_SECTIONS.some((s) => s.id === section) ? section : 'users'
  return (
    <div className="stack">
      {tab === 'users' && <Users />}
      {tab === 'keywords' && <Keywords />}
      {tab === 'machine_make' && <MasterList title="Machine Make" loader={api.machineMakes} saver={api.saveMachineMake} hasCategory />}
      {tab === 'model' && <MasterList title="Model" loader={api.models} saver={api.saveModel} />}
      {tab === 'machine' && <MasterList title="Machine" loader={api.machines} saver={api.saveMachine} />}
      {tab === 'enquiry' && <Channels purpose="buyer_enquiry" title="Buyer-Enquiry Receiving Channels" />}
      {tab === 'proposal' && <Channels purpose="supplier_proposal" title="Supplier-Proposal Receiving Channels" />}
      {tab === 'templates' && <Templates />}
      {tab === 'integrations' && <Integrations />}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/index.js'
import { StatusBadge, money, fmtDate } from '../components/ui.jsx'

function Kpi({ label, value, foot, ico, tint, to }) {
  const inner = (
    <div className="card kpi">
      <div className="k-label"><span className="k-ico" style={{ background: tint[0], color: tint[1] }}>{ico}</span>{label}</div>
      <div className="k-value">{value}</div>
      <div className="k-foot">{foot}</div>
    </div>
  )
  return to ? <Link to={to}>{inner}</Link> : inner
}

export default function Dashboard() {
  const [d, setD] = useState(null)
  useEffect(() => { api.dashboard().then(setD) }, [])

  if (!d) return <div className="empty"><div className="big">⏳</div>Loading…</div>

  const waTotal = d.byChannel?.whatsapp || 0
  const emTotal = d.byChannel?.email || 0
  const waPct = Math.round((waTotal / Math.max(d.enquiries, 1)) * 100)

  return (
    <div className="stack">
      <div className="grid kpi-grid">
        <Kpi label="Buyer Enquiries" value={d.enquiries.toLocaleString('en-IN')} foot="total captured" ico="📥" tint={['var(--info-050)', 'var(--info-600)']} to="/buyer-enquiry" />
        <Kpi label="Supplier Proposals" value={d.proposals} foot="per-machine quotes" ico="🧾" tint={['var(--warn-050)', 'var(--warn-600)']} to="/supplier-proposal" />
        <Kpi label="Buyer Quotations" value={d.quotations} foot="sent to buyers" ico="💹" tint={['var(--ok-050)', 'var(--ok-600)']} to="/buyer-quotation" />
        <Kpi label="Buyers · Suppliers" value={`${d.buyers} · ${d.suppliers}`} foot="in the database" ico="🏭" tint={['var(--purple-050)', 'var(--purple-600)']} />
      </div>

      <div className="card">
        <div className="card-head"><h3>Enquiry Channels</h3><span className="hint">how buyers reach us</span></div>
        <div className="card-pad">
          <div className="flex-between" style={{ marginBottom: 8 }}>
            <span className="t-sub">WhatsApp</span><span className="money">{waTotal.toLocaleString('en-IN')}</span>
          </div>
          <div className="conf-bar"><div className="conf-fill" style={{ width: `${waPct}%` }} /></div>
          <div className="flex-between" style={{ margin: '14px 0 8px' }}>
            <span className="t-sub">Email</span><span className="money">{emTotal.toLocaleString('en-IN')}</span>
          </div>
          <div className="conf-bar"><div className="conf-fill" style={{ width: `${100 - waPct}%`, background: 'var(--teal-600)' }} /></div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h3>Recent Enquiries</h3><Link to="/buyer-enquiry" className="btn btn-outline btn-sm">View all</Link></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Ref</th><th>Buyer</th><th>Machine</th><th>Channel</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
              {d.recent.map((e) => (
                <tr key={e.id}>
                  <td className="t-main">{e.ref}</td>
                  <td>{e.buyer_name}<div className="t-sub">{e.buyer_company}</div></td>
                  <td>{e.machine}<div className="t-sub">{e.category} · qty {e.quantity}</div></td>
                  <td><span className="badge b-chan">{e.channel}</span></td>
                  <td><StatusBadge status={e.status} /></td>
                  <td className="t-sub">{fmtDate(e.received_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

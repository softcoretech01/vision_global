import { NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useStore } from '../store/useStore.jsx'
import { ADMIN_SECTIONS } from '../pages/Administration.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', ico: '▤', end: true },
  { to: '/buyer-enquiry', label: 'Buyer Enquiry', ico: '📥' },
  { to: '/supplier-proposal', label: 'Supplier Proposal', ico: '🧾' },
  { to: '/buyer-quotation', label: 'Buyer Quotation', ico: '💹' },
  {
    to: '/administration', label: 'Administration', ico: '⚙️',
    children: ADMIN_SECTIONS.map((s) => ({ to: `/administration/${s.id}`, label: s.label, ico: s.ico })),
  },
]

const TITLES = {
  '/': ['Dashboard', 'Overview of enquiries, proposals & quotations'],
  '/buyer-enquiry': ['Buyer Enquiry', 'All buyer enquiries · filter by date & channel'],
  '/supplier-proposal': ['Supplier Proposal', 'Supplier quotes from Email/WhatsApp — one row per machine'],
  '/buyer-quotation': ['Buyer Quotation', 'Quotations sent to buyers · follow-up & chat'],
  '/administration': ['Administration', 'Users, channel configuration & message templates'],
}

export default function Layout({ children }) {
  const { logout, user, usingMock } = useStore()
  const loc = useLocation()
  const base = '/' + (loc.pathname.split('/')[1] || '')
  const [title, sub] = TITLES[base] || ['Vision Global', '']
  const onAdmin = base === '/administration'
  const [adminOpen, setAdminOpen] = useState(onAdmin)
  useEffect(() => { if (onAdmin) setAdminOpen(true) }, [onAdmin])
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('vg_sidebar_collapsed') === '1' } catch { return false }
  })
  const toggleCollapsed = () => setCollapsed((c) => {
    const next = !c
    try { localStorage.setItem('vg_sidebar_collapsed', next ? '1' : '0') } catch { /* ignore */ }
    return next
  })

  return (
    <div className={'app-shell' + (collapsed ? ' collapsed' : '')}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="logo-badge small">VG</div>
          <span className="brand-text">Vision Global</span>
          <button className="sidebar-toggle" onClick={toggleCollapsed}
            title={collapsed ? 'Expand menu' : 'Collapse menu'} aria-label="Toggle menu">
            {collapsed ? '»' : '«'}
          </button>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            n.children ? (
              <div key={n.to} className="nav-group">
                <NavLink to={n.to} title={n.label}
                  className={'nav-item' + (onAdmin ? ' active' : '')}
                  onClick={(e) => { if (onAdmin && !collapsed) { e.preventDefault(); setAdminOpen((o) => !o) } }}>
                  <span className="nav-ico">{n.ico}</span><span className="nav-label">{n.label}</span>
                  <span className="nav-caret">{adminOpen ? '▾' : '▸'}</span>
                </NavLink>
                {adminOpen && !collapsed && (
                  <div className="nav-sub">
                    {n.children.map((c) => (
                      <NavLink key={c.to} to={c.to} title={c.label}
                        className={({ isActive }) => 'nav-subitem' + (isActive ? ' active' : '')}>
                        <span className="nav-sub-ico">{c.ico}</span><span className="nav-label">{c.label}</span>
                      </NavLink>
                    ))}
                  </div>
                )}
                {collapsed && (
                  <div className="nav-sub nav-sub-flyout">
                    <div className="flyout-title">{n.label}</div>
                    {n.children.map((c) => (
                      <NavLink key={c.to} to={c.to} title={c.label}
                        className={({ isActive }) => 'nav-subitem' + (isActive ? ' active' : '')}>
                        <span className="nav-sub-ico">{c.ico}</span><span className="nav-label">{c.label}</span>
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <NavLink key={n.to} to={n.to} end={n.end} title={n.label}
                className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
                <span className="nav-ico">{n.ico}</span><span className="nav-label">{n.label}</span>
              </NavLink>
            )
          ))}
        </nav>
        <div className="sidebar-foot">
          {usingMock && <div className="nav-item subtle" style={{ cursor: 'default' }}><span className="nav-ico">◐</span><span className="nav-label">Demo data (no backend)</span></div>}
          <button className="nav-item as-btn" onClick={logout} title="Logout" style={{ cursor: 'pointer' }}>
            <span className="nav-ico">🚪</span><span className="nav-label">Logout</span>
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div>
            <h2>{title}</h2>
            <p className="page-sub">{sub}</p>
          </div>
          <div className="topbar-right">
            <span className="user-chip"><span className="user-avatar">{(user?.name || 'A')[0]}</span> {user?.name || 'Admin'}</span>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}

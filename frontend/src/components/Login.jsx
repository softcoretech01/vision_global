import { useState } from 'react'
import { useStore } from '../store/useStore.jsx'

function HeroArt() {
  // Self-contained warm illustration (procurement / supply theme) — no external asset.
  return (
    <svg className="hero-svg" viewBox="0 0 640 820" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
      {/* soft sun / glow */}
      <circle cx="540" cy="120" r="150" fill="rgba(255,255,255,.14)" />
      <circle cx="540" cy="120" r="95" fill="rgba(255,255,255,.12)" />
      {/* floating gears */}
      <g fill="none" stroke="rgba(255,255,255,.28)" strokeWidth="6">
        <circle cx="120" cy="150" r="34" />
        <circle cx="120" cy="150" r="14" />
        <circle cx="200" cy="210" r="22" />
      </g>
      {/* dotted supply route + pins */}
      <path d="M60 470 C 180 400, 300 540, 460 450 S 640 470, 700 440" fill="none" stroke="rgba(255,255,255,.4)" strokeWidth="3" strokeDasharray="4 10" strokeLinecap="round" />
      <g fill="rgba(255,255,255,.85)">
        <circle cx="60" cy="470" r="7" /><circle cx="460" cy="450" r="7" />
      </g>
      {/* warehouse / factory skyline */}
      <g fill="rgba(0,0,0,.14)">
        <rect x="40" y="620" width="150" height="160" rx="6" />
        <polygon points="40,620 115,575 190,620" />
        <rect x="210" y="560" width="120" height="220" rx="6" />
        <rect x="245" y="500" width="18" height="70" />
        <rect x="280" y="500" width="18" height="70" />
        <rect x="350" y="650" width="140" height="130" rx="6" />
        <rect x="510" y="600" width="110" height="180" rx="6" />
      </g>
      {/* windows */}
      <g fill="rgba(255,255,255,.3)">
        <rect x="70" y="650" width="22" height="22" rx="3" /><rect x="110" y="650" width="22" height="22" rx="3" /><rect x="150" y="650" width="22" height="22" rx="3" />
        <rect x="70" y="695" width="22" height="22" rx="3" /><rect x="110" y="695" width="22" height="22" rx="3" /><rect x="150" y="695" width="22" height="22" rx="3" />
        <rect x="540" y="630" width="22" height="22" rx="3" /><rect x="580" y="630" width="22" height="22" rx="3" />
      </g>
      {/* delivery truck */}
      <g transform="translate(360,700)" fill="rgba(255,255,255,.9)">
        <rect x="0" y="0" width="70" height="46" rx="5" />
        <path d="M70 12 h26 l16 20 v14 h-42 z" />
        <circle cx="20" cy="52" r="10" fill="rgba(0,0,0,.35)" /><circle cx="92" cy="52" r="10" fill="rgba(0,0,0,.35)" />
        <circle cx="20" cy="52" r="4" /><circle cx="92" cy="52" r="4" />
      </g>
    </svg>
  )
}

export default function Login() {
  const { login } = useStore()
  const [u, setU] = useState('admin')
  const [p, setP] = useState('admin')
  const [err, setErr] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    const ok = await login(u, p)
    if (!ok) setErr(true)
  }

  return (
    <div className="login-split">
      <div className="login-hero">
        <HeroArt />
        <div className="hero-top">
          <div className="hero-eyebrow">TECHSPIRE PRESENTS</div>
          <h1>Vision Global</h1>
          <p className="hero-tagline">
            One platform to automate your buyer-to-supplier procurement — from
            enquiry intake to AI matching, quotations, margin and approval.
          </p>
        </div>
      </div>

      <div className="login-panel">
        <div className="login-card">
          <div className="login-brand">
            <div className="logo-badge">VG</div>
            <div>
              <h1>Vision Global</h1>
              <p>by Techspire · Proposal Automation</p>
            </div>
          </div>

          <div className="login-welcome">Welcome back 👋</div>
          <p>Sign in to the procurement control tower</p>

          <form className="login-form" onSubmit={submit} autoComplete="off">
            <label>Username
              <input value={u} onChange={(e) => { setU(e.target.value); setErr(false) }} required />
            </label>
            <label>Password
              <input type="password" value={p} onChange={(e) => { setP(e.target.value); setErr(false) }} required />
            </label>
            {err && <div className="login-error">Invalid credentials. Try admin / admin.</div>}
            <button type="submit" className="btn btn-primary btn-block">Sign In</button>
            <p className="login-hint">Demo login — <strong>admin</strong> / <strong>admin</strong></p>
          </form>

          <div className="login-ai-note">
            <span className="ai-dot" /> AI-assisted intake · WhatsApp &amp; Email
          </div>
        </div>
      </div>
    </div>
  )
}

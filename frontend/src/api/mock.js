/* ===================================================================
   MOCK API — mirrors the FastAPI contract exactly, in-memory.
   Lets the whole frontend run with no backend. When VITE_API_URL is
   set (FastAPI), src/api/index.js uses the real client instead and
   this file is ignored.
   =================================================================== */

const CATALOG = [
  { category: 'CNC & Machining', machines: ['CNC VMC', 'CNC Lathe', 'Turning Center', 'Vertical Machining Center'] },
  { category: 'Packaging', machines: ['Filling Machine', 'Sealing Machine', 'Shrink Wrapper', 'Cartoning Machine'] },
  { category: 'Printing', machines: ['Flexo Printing Machine', 'Offset Press', 'Rotogravure Machine'] },
  { category: 'Plastic & Injection', machines: ['Injection Moulding Machine', 'Blow Moulding Machine', 'Extruder'] },
  { category: 'Food Processing', machines: ['Dough Mixer', 'Baking Oven', 'Pulverizer', 'Roaster'] },
  { category: 'Textile', machines: ['Knitting Machine', 'Power Loom', 'Spinning Frame'] },
]
const FIRST = ['Ravi', 'Anand', 'Suresh', 'Meena', 'Karthik', 'Divya', 'Arun', 'Priya', 'Vikram', 'Latha', 'Mohan', 'Sneha']
const LAST = ['Kumar', 'Textiles', 'Industries', 'Foods', 'Enterprises', 'Mills', 'Traders', 'Exports', 'Pvt Ltd', 'Works']
const SEG = ['cold', 'cold', 'cold', 'hot', 'hot', 'very_hot']
const CHANNELS = ['whatsapp', 'email']

const rnd = (a) => a[Math.floor(Math.random() * a.length)]
const rint = (n) => Math.floor(Math.random() * n)
const isoDaysAgo = (d) => new Date(Date.now() - d * 86400000 - rint(86400000)).toISOString()
const nowISO = () => new Date().toISOString()
const delay = (v, ms = 120) => new Promise((r) => setTimeout(() => r(v), ms))
const inRange = (iso, from, to) => {
  if (!iso) return !from && !to
  const d = iso.slice(0, 10)
  if (from && d < from) return false
  if (to && d > to) return false
  return true
}

function build() {
  const buyers = []
  for (let i = 1; i <= 250; i++) {
    buyers.push({
      id: i, name: `${rnd(FIRST)} ${rnd(LAST)}`, company: `${rnd(LAST)} ${rnd(['Group', 'Co', 'Mfg', 'Industries'])}`,
      phone: `+91 9${rint(900000000) + 100000000}`, email: `buyer${i}@example.in`, segment: rnd(SEG),
    })
  }
  const suppliers = [
    { id: 1, name: 'Precision CNC Works', phone: '+91 98400 11223', email: 'sales@precisioncnc.in', location: 'Coimbatore' },
    { id: 2, name: 'PackPro Machinery', phone: '+91 90030 77881', email: 'info@packpro.in', location: 'Ahmedabad' },
    { id: 3, name: 'FlexoPrint Tech', phone: '+91 93450 66332', email: 'quote@flexoprint.in', location: 'Delhi' },
    { id: 4, name: 'PolyMould Industries', phone: '+91 98210 55447', email: 'sales@polymould.in', location: 'Vadodara' },
    { id: 5, name: 'FoodTech Equipments', phone: '+91 90470 88990', email: 'rfq@foodtecheq.in', location: 'Chennai' },
    { id: 6, name: 'WeaveWell Textile Mch', phone: '+91 94430 33221', email: 'info@weavewell.in', location: 'Tirupur' },
  ]
  const enquiries = []
  for (let i = 1; i <= 1200; i++) {
    const cat = rnd(CATALOG)
    const machine = rnd(cat.machines)
    const b = rnd(buyers)
    enquiries.push({
      id: i, ref: `ENQ-${2000 + i}`, buyer_id: b.id, buyer_name: b.name, buyer_company: b.company, segment: b.segment,
      channel: rnd(CHANNELS), machine, category: cat.category, quantity: 1 + rint(5), specs: `${5 + rint(40)} kW`,
      status: rnd(['new', 'quoted', 'closed']), received_at: isoDaysAgo(rint(180)),
    })
  }
  const proposalItems = []
  let pid = 0
  for (let e = 0; e < 40; e++) {
    const s = rnd(suppliers)
    const channel = rnd(CHANNELS)
    const n = 1 + rint(3)
    for (let m = 0; m < n; m++) {
      const cat = rnd(CATALOG)
      const machine = rnd(cat.machines)
      proposalItems.push({
        id: ++pid, supplier_id: s.id, supplier_name: s.name, supplier_phone: s.phone, supplier_email: s.email,
        source_channel: channel, machine, category: cat.category, photos: [], price: 300000 + rint(1500000),
        margin_pct: rnd([10, 12, 15, 18, 20]), buyer_segment: 'everyone', photo_status: 'none', created_at: isoDaysAgo(rint(60)),
      })
    }
  }
  const channels = [
    { id: 1, purpose: 'buyer_enquiry', type: 'email', label: 'Buyer intake email', address: 'enquiry@etex.in', active: 1 },
    { id: 3, purpose: 'supplier_proposal', type: 'email', label: 'Supplier proposal inbox', address: 'kabileshv53@gmail.com', active: 1 },
  ]
  const templates = [
    { id: 1, kind: 'buyer_quotation', channel: 'any', name: 'Default quotation', subject: 'Your quotation from Vision Global', body: 'Hello {{buyer}},\n\nHere is our offer for {{machine}}:\nPrice: {{amount}}\n\nRegards,\nVision Global', active: 1 },
    { id: 2, kind: 'followup', channel: 'any', name: 'Default follow-up', subject: 'Following up on your quotation', body: 'Hi {{buyer}}, just following up on the quotation for {{machine}}. Shall we proceed?', active: 1 },
    { id: 3, kind: 'whatsapp_response', channel: 'whatsapp', name: 'Auto WhatsApp response', subject: '', body: 'Thanks {{buyer}}, we received your enquiry for {{machine}} and will revert shortly.', active: 1 },
    { id: 4, kind: 'photo_request', channel: 'any', name: 'Photo request', subject: 'Please share machine photos', body: 'Hi {{supplier}}, kindly share clear photos of the {{machine}} for buyer review.', active: 1 },
  ]
  const users = [
    { id: 1, name: 'System Administrator', email: 'admin@etex.local', phone: '', role: 'super_admin', status: 'active', created_at: nowISO() },
  ]
  return { buyers, suppliers, enquiries, proposalItems, quotations: [], chat: {}, followups: {}, channels, templates, users, seqQ: 0, seqId: 1000 }
}

const DB = build()
const buyerById = (id) => DB.buyers.find((b) => b.id === id)

export const api = {
  login: (email, password) => {
    const ok = password === 'admin' && (email === 'admin' || email === 'admin@etex.local')
    if (!ok) return Promise.reject(new Error('Invalid credentials'))
    return delay({ token: 'mock-token', user: { id: 1, name: 'System Administrator', email: 'admin@etex.local', role: 'super_admin' } })
  },

  enquiries: ({ channel, from, to, q, page = 1, pageSize = 50 } = {}) => {
    let rows = DB.enquiries
    if (channel) rows = rows.filter((e) => e.channel === channel)
    if (from || to) rows = rows.filter((e) => inRange(e.received_at, from, to))
    if (q) {
      const s = q.toLowerCase()
      rows = rows.filter((e) => e.machine.toLowerCase().includes(s) || e.ref.toLowerCase().includes(s) || e.buyer_name.toLowerCase().includes(s))
    }
    rows = [...rows].sort((a, b) => b.received_at.localeCompare(a.received_at))
    const total = rows.length
    const lim = Math.min(Number(pageSize) || 50, 200)
    const off = (Math.max(Number(page) || 1, 1) - 1) * lim
    return delay({ rows: rows.slice(off, off + lim), total, page: Number(page) || 1, pageSize: lim })
  },

  proposals: ({ from, to, supplier, q } = {}) => {
    let rows = DB.proposalItems
    if (from || to) rows = rows.filter((p) => inRange(p.created_at, from, to))
    if (supplier) rows = rows.filter((p) => p.supplier_id === Number(supplier))
    if (q) {
      const s = q.toLowerCase()
      rows = rows.filter((p) => p.machine.toLowerCase().includes(s) || p.supplier_name.toLowerCase().includes(s))
    }
    rows = [...rows].map((p) => {
      const isSent = p.status === 'sent' || p.quotation_sent || DB.quotations.some((q) => q.proposal_item_id === p.id)
      return { ...p, status: isSent ? 'sent' : (p.status || 'new'), quotation_sent: isSent }
    }).sort((a, b) => b.created_at.localeCompare(a.created_at))
    return delay({ rows })
  },

  createEnquiry: (data) => delay({ ok: true, ref: 'ENQ-mock', id: Date.now() }),

  getProposal: (id) => {
    const it = DB.proposalItems.find((p) => p.id === Number(id))
    if (!it) return Promise.reject(new Error('not found'))
    return delay({ row: { ...it } })
  },

  updateProposal: (id, patch) => {
    const it = DB.proposalItems.find((p) => p.id === Number(id))
    if (it) Object.assign(it, patch)
    return delay({ ok: true })
  },

  enquiredBuyers: (id) => {
    const it = DB.proposalItems.find((p) => p.id === Number(id))
    const m = (it?.machine || it?.model || '').toLowerCase()
    let matches = DB.enquiries.filter((e) => !m || e.machine.toLowerCase().includes(m) || m.includes(e.machine.toLowerCase()))
    if (!matches.length) matches = DB.enquiries.slice(0, 15)
    const seen = new Set()
    const buyers = []
    for (const e of matches) {
      if (seen.has(e.buyer_id)) continue
      seen.add(e.buyer_id)
      const b = buyerById(e.buyer_id)
      if (b) {
        const namePart = b.name && b.company && b.name !== b.company ? `${b.name} / ${b.company}` : (b.company || b.name || 'Buyer')
        let label = b.city ? `${namePart}-${b.city}` : namePart
        if (b.segment === 'cold' && !label.toLowerCase().includes('do not call')) {
          label = `(Do Not Call)${label}`
        }
        buyers.push({
          id: b.id,
          label,
          name: b.name,
          company: b.company,
          city: b.city,
          phone: b.phone,
          email: b.email,
          segment: b.segment,
          enquiry_id: e.id,
          machine: e.machine,
          model: e.model || e.machine,
        })
      }
    }
    return delay({ buyers })
  },

  uploadProposalImages: (id, formData) => {
    const it = DB.proposalItems.find((p) => p.id === Number(id))
    if (!it) return Promise.reject(new Error('not found'))
    it.photos = it.photos || []
    const newPhotos = ['https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=500']
    it.photos.push(...newPhotos)
    return delay({ ok: true, uploaded: newPhotos, photos: it.photos })
  },

  models: () => delay({ rows: [
    { id: 1, name: 'Somet Rapier', active: 1 },
    { id: 2, name: 'Sulzer Projectile', active: 1 },
    { id: 3, name: 'Super Excel', active: 1 },
    { id: 4, name: 'Calandering Machine', active: 1 },
    { id: 5, name: 'Picanol Rapier', active: 1 },
  ] }),

  machines: () => delay({ rows: [
    { id: 1, name: 'Somet', active: 1 },
    { id: 2, name: 'Sulzer', active: 1 },
    { id: 3, name: 'Toyoda', active: 1 },
    { id: 4, name: 'Picanol', active: 1 },
    { id: 5, name: 'Corino', active: 1 },
  ] }),

  machineMakes: () => delay({ rows: [
    { id: 1, name: 'Somet', active: 1 },
    { id: 2, name: 'Sulzer', active: 1 },
  ] }),

  bulkSegment: (buyer_segment, ids) => {
    const set = ids && ids.length ? new Set(ids) : null
    DB.proposalItems.forEach((p) => { if (!set || set.has(p.id)) p.buyer_segment = buyer_segment })
    return delay({ ok: true })
  },

  recipients: (id) => delay({ machine: '', segment: 'everyone', count: 0, buyers: [] }),

  requestPhoto: (id) => {
    const it = DB.proposalItems.find((p) => p.id === Number(id))
    if (!it) return Promise.reject(new Error('not found'))
    it.photo_status = 'requested'
    return delay({ ok: true, channel: it.source_channel, simulated: true })
  },

  sendProposal: (id) => {
    const it = DB.proposalItems.find((p) => p.id === Number(id))
    if (!it) return Promise.reject(new Error('not found'))
    it.status = 'sent'
    it.quotation_sent = true
    const seg = it.buyer_segment
    const segs = Array.isArray(seg)
      ? seg
      : (typeof seg === 'string' ? seg.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean) : ['everyone'])
    const matches = DB.enquiries.filter((e) => {
      if (e.machine !== it.machine) return false
      if (segs.includes('everyone') || segs.length === 0) return true
      return segs.includes(e.segment?.toLowerCase())
    })
    const seen = new Set()
    const amount = Math.round(Number(it.price) * (1 + Number(it.margin_pct) / 100))
    let sent = 0
    for (const e of matches) {
      if (seen.has(e.buyer_id)) continue
      seen.add(e.buyer_id)
      const b = buyerById(e.buyer_id)
      DB.seqQ++
      const qrow = {
        id: DB.seqQ, ref: `QT-${3000 + DB.seqQ}`, buyer_id: b.id, buyer_name: b.name, buyer_company: b.company,
        machine: it.machine, base_price: it.price, margin_pct: it.margin_pct, amount, channel: e.channel,
        status: 'sent', sent_at: nowISO(), proposal_item_id: it.id,
      }
      DB.quotations.unshift(qrow)
      const body = `Hello ${b.name}, our offer for ${it.machine}: ₹${amount.toLocaleString('en-IN')}.`;
      (DB.chat[b.id] = DB.chat[b.id] || []).push({ direction: 'out', channel: e.channel, body, created_at: nowISO() })
      sent++
    }
    return delay({ ok: true, sent, amount, matchedBuyers: sent })
  },

  quotations: ({ from, to, q, page = 1, pageSize = 50 } = {}) => {
    let rows = DB.quotations
    if (from || to) rows = rows.filter((x) => inRange(x.sent_at, from, to))
    if (q) {
      const s = q.toLowerCase()
      rows = rows.filter((x) => x.machine.toLowerCase().includes(s) || x.buyer_name.toLowerCase().includes(s) || x.ref.toLowerCase().includes(s))
    }
    const total = rows.length
    const lim = Math.min(Number(pageSize) || 50, 200)
    const off = (Math.max(Number(page) || 1, 1) - 1) * lim
    const paged = rows.slice(off, off + lim).map((x) => ({ ...x, followup: DB.followups[x.id] || null }))
    return delay({ rows: paged, total })
  },

  quotation: (id) => {
    const row = DB.quotations.find((x) => x.id === Number(id))
    if (!row) return Promise.reject(new Error('not found'))
    const b = buyerById(row.buyer_id)
    return delay({ row: { ...row, buyer_phone: b?.phone, buyer_email: b?.email } })
  },

  setFollowup: (id, frequency) => { DB.followups[Number(id)] = frequency; return delay({ ok: true }) },
  resolveSupport: () => delay({ ok: true }),
  replyQuotation: () => delay({ ok: true, channel: 'whatsapp', simulated: true }),

  chat: (id) => {
    const row = DB.quotations.find((x) => x.id === Number(id))
    return delay({ rows: row ? (DB.chat[row.buyer_id] || []) : [] })
  },

  channels: (purpose) => delay({ rows: DB.channels.filter((c) => !purpose || c.purpose === purpose) }),
  saveChannel: (data) => {
    if (data.id) { Object.assign(DB.channels.find((c) => c.id === data.id), data) } else { data.id = Math.max(0, ...DB.channels.map((c) => c.id)) + 1; DB.channels.push({ active: 1, ...data }) }
    return delay({ ok: true, id: data.id })
  },
  deleteChannel: (id) => { DB.channels = DB.channels.filter((c) => c.id !== Number(id)); return delay({ ok: true }) },

  templates: () => delay({ rows: DB.templates }),
  saveTemplate: (id, data) => { Object.assign(DB.templates.find((t) => t.id === Number(id)), data); return delay({ ok: true }) },
  createTemplate: (data) => { const nid = Math.max(0, ...DB.templates.map((t) => t.id)) + 1; DB.templates.push({ id: nid, channel: 'any', active: 1, ...data }); return delay({ id: nid }) },
  integrations: () => delay({ email: { configured: false, account: '', smtp_host: '', smtp_port: '', imap_host: '', send_ready: false, fetch_ready: false, from: '', auto_fetch: false, fetch_interval: 180 } }),
  testEmail: () => delay({ ok: false, detail: 'Mock mode — no live SMTP configured.' }),
  keywords: () => delay({ rows: (DB.keywords = DB.keywords || []) }),
  addKeyword: (word) => { DB.keywords = DB.keywords || []; if (word && !DB.keywords.find((k) => k.word === word)) DB.keywords.push({ id: Date.now(), word }); return delay({ ok: true }) },
  deleteKeyword: (id) => { DB.keywords = (DB.keywords || []).filter((k) => k.id !== Number(id)); return delay({ ok: true }) },
  fetchEmails: () => delay({ ok: true, fetched: 0, matched: 0, detail: 'Mock mode — connect Gmail on the real backend to fetch.' }),

  users: () => delay({ rows: DB.users }),
  saveUser: (id, data) => {
    if (id) { Object.assign(DB.users.find((u) => u.id === Number(id)), data) } else { const nid = Math.max(0, ...DB.users.map((u) => u.id)) + 1; DB.users.push({ id: nid, status: 'active', created_at: nowISO(), ...data }) }
    return delay({ ok: true })
  },

  dashboard: () => {
    const byChannel = { whatsapp: 0, email: 0 }
    DB.enquiries.forEach((e) => { byChannel[e.channel]++ })
    return delay({
      enquiries: DB.enquiries.length,
      proposals: DB.proposalItems.length,
      quotations: DB.quotations.length,
      buyers: DB.buyers.length,
      suppliers: DB.suppliers.length,
      byChannel,
      recent: [...DB.enquiries].sort((a, b) => b.received_at.localeCompare(a.received_at)).slice(0, 8),
    })
  },
}

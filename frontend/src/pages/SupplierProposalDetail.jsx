import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/index.js'
import { useStore } from '../store/useStore.jsx'
import { fmtDate, Modal } from '../components/ui.jsx'

const PRIORITIES = ['Very high', 'High', 'Medium', 'Low']
const THROUGHS = ['e_mail', 'whatsapp', 'phone']
const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'CNY']
const RATE_TYPES = ['Fixed', 'Negotiable', 'Per unit', 'Lot']
const PRICE_TERMS = ['Ex-works', 'FOB', 'CIF', 'C&F', 'Delivered']

const SAVE_FIELDS = [
  'machine', 'model', 'width', 'mode', 'machine_color', 'year', 'quantity',
  'rate_type', 'rate', 'price_term', 'currency', 'priority', 'machine_name', 'through',
  'payment_term', 'purchased_by', 'remarks', 'confidential', 'price', 'margin_pct',
  'accessories', 'waiting_list', 'photos'
]

/* Full-page Supplier-Proposal details editor with Waiting List, Accessories, and Image Upload. */
export default function SupplierProposalDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { flash } = useStore()

  const [f, setF] = useState(null)
  const [models, setModels] = useState([])
  const [machines, setMachines] = useState([])
  const [saving, setSaving] = useState(false)
  const [notFound, setNotFound] = useState(false)

  // Waiting list dual-box state
  const [availableBuyers, setAvailableBuyers] = useState([])
  const [selectedAvailable, setSelectedAvailable] = useState([])
  const [selectedWaiting, setSelectedWaiting] = useState([])

  // Image upload state
  const [uploading, setUploading] = useState(false)
  const [activePreview, setActivePreview] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    let isMounted = true

    api.getProposal(id)
      .then((d) => {
        if (!isMounted) return
        const row = d.row || {}

        // Normalize waiting_list
        let currentWaiting = []
        if (Array.isArray(row.waiting_list)) {
          currentWaiting = row.waiting_list
        } else if (typeof row.waiting_list === 'string') {
          try {
            currentWaiting = JSON.parse(row.waiting_list) || []
          } catch {
            currentWaiting = []
          }
        }
        row.waiting_list = currentWaiting
        row.photos = Array.isArray(row.photos) ? row.photos : []
        row.accessories = row.accessories || ''
        setF({ ...row })

        // Fetch enquired buyers for this machine
        api.enquiredBuyers(id)
          .then((res) => {
            if (!isMounted) return
            const buyers = res.buyers || []
            const waitingIds = new Set(
              currentWaiting.map((w) => String(typeof w === 'object' ? w.id : w))
            )
            setAvailableBuyers(buyers.filter((b) => !waitingIds.has(String(b.id))))
          })
          .catch(() => {
            // Fallback: query all enquiries to show candidate buyers
            api.enquiries()
              .then((enqRes) => {
                if (!isMounted) return
                const rows = enqRes.rows || []
                const seen = new Set()
                const list = []
                rows.forEach((e) => {
                  const bId = e.buyer_id || e.id
                  if (!seen.has(bId)) {
                    seen.add(bId)
                    const name = e.buyer_name || e.name || 'Buyer'
                    const comp = e.buyer_company || e.company || ''
                    const city = e.buyer_city || e.city || ''
                    const namePart = comp && name && comp !== name ? `${name} / ${comp}` : (comp || name)
                    let label = city ? `${namePart}-${city}` : namePart
                    if (e.segment === 'cold' && !label.toLowerCase().includes('do not call')) {
                      label = `(Do Not Call)${label}`
                    }
                    list.push({ id: bId, label, name, company: comp, city })
                  }
                })
                const waitingIds = new Set(
                  currentWaiting.map((w) => String(typeof w === 'object' ? w.id : w))
                )
                setAvailableBuyers(list.filter((b) => !waitingIds.has(String(b.id))))
              })
              .catch(() => {})
          })
      })
      .catch(() => setNotFound(true))

    api.models().then((d) => setModels((d.rows || []).filter((r) => r.active))).catch(() => {})
    api.machines().then((d) => setMachines((d.rows || []).filter((r) => r.active))).catch(() => {})

    return () => { isMounted = false }
  }, [id])

  const back = () => navigate('/supplier-proposal')
  const set = (k, v) => setF((o) => ({ ...o, [k]: v }))

  // Move selected available buyers to waiting list
  const moveToWaiting = (targetIds) => {
    const ids = targetIds || selectedAvailable
    if (!ids || !ids.length) return
    const idSet = new Set(ids.map(String))
    const toMove = availableBuyers.filter((b) => idSet.has(String(b.id)))
    const remaining = availableBuyers.filter((b) => !idSet.has(String(b.id)))
    setAvailableBuyers(remaining)
    set('waiting_list', [...(f.waiting_list || []), ...toMove])
    setSelectedAvailable([])
  }

  // Remove selected buyers from waiting list back to available
  const removeFromWaiting = (targetIds) => {
    const ids = targetIds || selectedWaiting
    if (!ids || !ids.length) return
    const idSet = new Set(ids.map(String))
    const currentWaiting = f.waiting_list || []
    const toRemove = currentWaiting.filter((w) =>
      idSet.has(String(typeof w === 'object' ? w.id : w))
    )
    const remaining = currentWaiting.filter(
      (w) => !idSet.has(String(typeof w === 'object' ? w.id : w))
    )
    set('waiting_list', remaining)
    setAvailableBuyers((prev) => [...prev, ...toRemove])
    setSelectedWaiting([])
  }

  // Handle image files selection
  const handleImageUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    try {
      const fd = new FormData()
      files.forEach((file) => fd.append('files', file))
      const res = await api.uploadProposalImages(f.id, fd)
      if (res && res.photos) {
        set('photos', res.photos)
        flash(`${files.length} image(s) uploaded successfully`)
      }
    } catch {
      // Fallback: convert to base64 data URLs for offline preview & saving
      const readers = files.map(
        (file) =>
          new Promise((resolve) => {
            const fr = new FileReader()
            fr.onload = (ev) => resolve(ev.target.result)
            fr.readAsDataURL(file)
          })
      )
      const urls = await Promise.all(readers)
      set('photos', [...(f.photos || []), ...urls])
      flash(`${files.length} image(s) added`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleClearImages = () => {
    if (fileInputRef.current) fileInputRef.current.value = ''
    if (f.photos && f.photos.length > 0) {
      if (window.confirm('Clear all uploaded images for this proposal?')) {
        set('photos', [])
        flash('Images cleared')
      }
    }
  }

  const removePhoto = (idx) => {
    const nextPhotos = (f.photos || []).filter((_, i) => i !== idx)
    set('photos', nextPhotos)
  }

  const save = async () => {
    setSaving(true)
    const body = {}
    SAVE_FIELDS.forEach((k) => { body[k] = f[k] })
    try {
      await api.updateProposal(f.id, body)
      flash('Proposal saved')
      back()
    } catch (err) {
      flash(err.message || 'Could not save', 'err')
    } finally {
      setSaving(false)
    }
  }

  if (notFound) return (
    <div className="card card-pad">
      <p className="muted">Proposal not found.</p>
      <button className="btn btn-outline btn-sm" onClick={back}>‹ Back to Supplier Proposal</button>
    </div>
  )
  if (!f) return <div className="card card-pad muted">Loading…</div>

  const final = Math.round(Number(f.price || 0) * (1 + Number(f.margin_pct || 0) / 100))
  const sel = (label, k, opts, req) => (
    <div className="field"><label>{label}{req ? ' *' : ''}</label>
      <select value={f[k] || ''} onChange={(e) => set(k, e.target.value)}>
        <option value="">-- Select --</option>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select></div>
  )
  const txt = (label, k, type) => (
    <div className="field"><label>{label}</label>
      <input type={type || 'text'} value={f[k] ?? ''} onChange={(e) => set(k, e.target.value)} /></div>
  )

  return (
    <div className="stack">
      <div className="page-actions">
        <button className="btn btn-outline btn-sm" onClick={back}>‹ Back</button>
        <div className="toolbar" style={{ marginLeft: 'auto' }}>
          <button className="btn btn-outline" onClick={back}>Cancel</button>
          <button className="btn btn-primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save'}</button>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Supplier Proposal Details — Pro No {f.pro_no || '—'}</h3>
          <span className="hint">{f.supplier_name} · {f.source_channel || 'email'}</span>
        </div>
        <div className="card-pad">
          <div className="form-grid">
            <div className="row-3">
              <div className="field"><label>Proposal No</label><input value={f.pro_no || ''} readOnly /></div>
              <div className="field"><label>Supplier Name</label><input value={f.supplier_name || ''} readOnly /></div>
              <div className="field"><label>Date</label><input value={fmtDate(f.received_at || f.created_at)} readOnly /></div>
            </div>
            <div className="row-3">
              {sel('Through', 'through', THROUGHS, true)}
              {txt('Payment Term', 'payment_term')}
              {txt('Purchased By', 'purchased_by')}
            </div>
            <div className="field"><label>Remarks</label>
              <textarea style={{ minHeight: 64 }} value={f.remarks || ''} onChange={(e) => set('remarks', e.target.value)} /></div>
            <label className="flex" style={{ gap: 8 }}><input type="checkbox" checked={!!f.confidential} onChange={(e) => set('confidential', e.target.checked)} /> Confidential</label>

            <div className="section-title">Details</div>
            <div className="row-3">
              {sel('Model Name', 'model', models.map((m) => m.name), true)}
              {txt('Width', 'width')}
              {txt('Mode', 'mode')}
            </div>
            <div className="row-3">
              {txt('Machine Color', 'machine_color')}
              {txt('Year', 'year')}
              {txt('Quantity', 'quantity')}
            </div>
            <div className="row-3">
              {sel('Rate Type', 'rate_type', RATE_TYPES)}
              {txt('Rate', 'rate')}
              {sel('Price Term', 'price_term', PRICE_TERMS)}
            </div>
            <div className="row-3">
              {sel('Currency', 'currency', CURRENCIES)}
              {sel('Priority', 'priority', PRIORITIES)}
              {sel('Machine Name', 'machine_name', machines.map((m) => m.name))}
            </div>

            <div className="section-title">Pricing</div>
            <div className="row-3">
              {txt('Base Price (₹)', 'price', 'number')}
              {txt('Margin %', 'margin_pct', 'number')}
              <div className="field"><label>Final (₹)</label><input value={final.toLocaleString('en-IN')} readOnly /></div>
            </div>

            {/* Waiting List, Accessories & Image Upload Section matching legacy reference */}
            <div className="waiting-list-box">
              <div className="waiting-list-title-bar">Waiting List</div>
              <div className="waiting-list-body">
                {/* Dual Listbox: Left (Enquired Buyers) -> Right (Waiting List) */}
                <div className="dual-listbox-wrap">
                  <div className="dual-listbox-col">
                    <label>Enquired Buyers ({availableBuyers.length})</label>
                    <select
                      multiple
                      className="dual-select"
                      value={selectedAvailable}
                      onChange={(e) => {
                        const vals = Array.from(e.target.selectedOptions, (o) => o.value)
                        setSelectedAvailable(vals)
                      }}
                      onDoubleClick={(e) => {
                        if (e.target.value) moveToWaiting([e.target.value])
                      }}
                    >
                      {availableBuyers.map((b) => (
                        <option key={b.id} value={b.id} title={b.label}>
                          {b.label}
                        </option>
                      ))}
                      {!availableBuyers.length && (
                        <option disabled style={{ fontStyle: 'italic', color: '#888' }}>
                          (No more matching buyers)
                        </option>
                      )}
                    </select>
                  </div>

                  <div className="dual-listbox-controls">
                    <button
                      type="button"
                      className="btn-transfer"
                      onClick={() => moveToWaiting()}
                      disabled={!selectedAvailable.length}
                      title="Move selected to Waiting List (->)"
                    >
                      -&gt;
                    </button>
                    <button
                      type="button"
                      className="btn-transfer"
                      onClick={() => removeFromWaiting()}
                      disabled={!selectedWaiting.length}
                      title="Remove selected from Waiting List (<-)"
                    >
                      &lt;-
                    </button>
                  </div>

                  <div className="dual-listbox-col">
                    <label>Waiting List ({(f.waiting_list || []).length})</label>
                    <select
                      multiple
                      className="dual-select"
                      value={selectedWaiting}
                      onChange={(e) => {
                        const vals = Array.from(e.target.selectedOptions, (o) => o.value)
                        setSelectedWaiting(vals)
                      }}
                      onDoubleClick={(e) => {
                        if (e.target.value) removeFromWaiting([e.target.value])
                      }}
                    >
                      {(f.waiting_list || []).map((w, idx) => {
                        const wid = typeof w === 'object' ? w.id : w
                        const wlabel = typeof w === 'object' ? (w.label || w.name) : `Buyer #${wid}`
                        return (
                          <option key={wid || idx} value={wid} title={wlabel}>
                            {wlabel}
                          </option>
                        )
                      })}
                    </select>
                  </div>
                </div>

                <hr className="waiting-list-divider" />

                {/* Accessories Textarea */}
                <div className="meta-field-row">
                  <div className="meta-field-label">Accessories</div>
                  <div className="meta-field-content">
                    <textarea
                      className="meta-textarea"
                      value={f.accessories || ''}
                      onChange={(e) => set('accessories', e.target.value)}
                      placeholder="e.g. 10xUsed Somet rapier model: Super Excel, year:1998, width in cm:210Cm&#10;20 Shafts&#10;Staubli 2688 Dobby&#10;Frame:12&#10;Feeder:3-4"
                    />
                  </div>
                </div>

                {/* Upload Image row */}
                <div className="meta-field-row" style={{ marginBottom: 0 }}>
                  <div className="meta-field-label">Upload Image</div>
                  <div className="meta-field-content">
                    <div className="upload-controls">
                      <input
                        type="file"
                        ref={fileInputRef}
                        multiple
                        accept="image/*"
                        onChange={handleImageUpload}
                        disabled={uploading}
                        style={{ fontSize: 13 }}
                      />
                      <button
                        type="button"
                        className="upload-clear-btn"
                        onClick={handleClearImages}
                        title="Clear chosen files / images"
                      >
                        Clear
                      </button>
                      {uploading && (
                        <span className="hint" style={{ color: 'var(--brand-600)' }}>
                          Uploading…
                        </span>
                      )}
                    </div>

                    {/* Image thumbnails preview */}
                    {f.photos && f.photos.length > 0 && (
                      <div className="photo-previews">
                        {f.photos.map((src, i) => (
                          <div
                            key={i}
                            className="photo-preview-item"
                            title="Click to view full image"
                            onClick={() => setActivePreview(src)}
                            style={{ cursor: 'pointer' }}
                          >
                            <img src={src} alt={`Machine photo ${i + 1}`} />
                            <button
                              type="button"
                              className="photo-preview-del"
                              title="Delete photo"
                              onClick={(e) => {
                                e.stopPropagation()
                                removePhoto(i)
                              }}
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="modal-foot">
              <button className="btn btn-outline" onClick={back}>Cancel</button>
              <button className="btn btn-primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save'}</button>
            </div>
          </div>
        </div>
      </div>

      {/* Image Preview Modal */}
      {activePreview && (
        <Modal title="Machine Image Preview" onClose={() => setActivePreview(null)} wide>
          <div style={{ textAlign: 'center', padding: 8 }}>
            <img
              src={activePreview}
              alt="Machine full preview"
              style={{ maxWidth: '100%', maxHeight: '75vh', borderRadius: 8, objectFit: 'contain' }}
            />
          </div>
        </Modal>
      )}
    </div>
  )
}

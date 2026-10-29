/* ===================================================================
   AI ENGINE (prototype)
   -------------------------------------------------------------------
   In production this is a Claude API call that reads the raw WhatsApp
   / email text and returns structured JSON. For an offline, runnable
   prototype we emulate that with an intent + entity extractor so the
   whole flow works with no keys or network.

   PRODUCTION SWAP (server-side):
     const res = await anthropic.messages.create({
       model: "claude-opus-4-8",
       max_tokens: 400,
       system: "Extract procurement enquiry as JSON {machine, category, quantity, specs}",
       messages: [{ role: "user", content: rawText }]
     })
   =================================================================== */

// Machine categories and the keywords that signal them.
export const CATEGORIES = [
  { key: 'CNC & Machining', keys: ['cnc', 'vmc', 'lathe', 'turning', 'milling', 'machining center', 'machining centre', 'grinding machine'] },
  { key: 'Packaging',       keys: ['packaging', 'packing', 'filling machine', 'sealing', 'wrapping', 'cartoning', 'labeling', 'labelling', 'shrink'] },
  { key: 'Printing',        keys: ['printing', 'flexo', 'offset', 'screen print', 'digital print', 'rotogravure'] },
  { key: 'Plastic & Injection', keys: ['injection molding', 'injection moulding', 'molding', 'moulding', 'extrusion', 'extruder', 'blow mold', 'blow mould'] },
  { key: 'Food Processing', keys: ['mixer', 'oven', 'grinder', 'baking', 'dough', 'roaster', 'pulverizer', 'pulveriser'] },
  { key: 'Textile',         keys: ['loom', 'knitting', 'spinning', 'weaving', 'dyeing', 'sewing', 'embroidery'] },
  { key: 'Material Handling', keys: ['conveyor', 'forklift', 'hoist', 'crane', 'stacker', 'pallet'] },
]

const QTY_RE = /(\d+)\s*(units?|nos?|pcs?|sets?|machines?|qty)?/i
const BUDGET_RE = /(?:budget|price|within|under|upto|up to)\s*[:\-]?\s*(?:rs|inr|₹|usd|\$)?\s*([\d,]+)/i

function titleCase(s) {
  return s.replace(/\w\S*/g, (t) => t.charAt(0).toUpperCase() + t.slice(1))
}

/**
 * Extract a structured enquiry from free WhatsApp / email text.
 * @returns {{machine, category, quantity, specs, budget, confidence}}
 */
export function extractEnquiry(rawText) {
  const text = (rawText || '').toLowerCase()
  let best = { key: 'Uncategorized', hits: 0, matched: null }

  for (const cat of CATEGORIES) {
    let hits = 0
    let matched = null
    for (const kw of cat.keys) {
      if (text.includes(kw)) {
        hits++
        if (!matched) matched = kw
      }
    }
    if (hits > best.hits) best = { key: cat.key, hits, matched }
  }

  // Machine name: prefer the matched keyword phrase, else first meaningful noun.
  let machine = best.matched ? titleCase(best.matched) : null
  if (!machine) {
    const m = text.match(/(?:need|want|require|looking for|enquiry for|quote for)\s+(?:a |an |the )?([a-z0-9 \-]{3,40})/i)
    if (m) machine = titleCase(m[1].trim().split(/\s+/).slice(0, 4).join(' '))
  }

  // Quantity
  let quantity = 1
  const q = text.match(QTY_RE)
  if (q && Number(q[1]) > 0 && Number(q[1]) < 100000) quantity = Number(q[1])

  // Budget (optional)
  let budget = null
  const b = rawText.match(BUDGET_RE)
  if (b) budget = Number(b[1].replace(/,/g, ''))

  // Specs = remaining signal words (dimensions, voltage, etc.)
  const specMatch = rawText.match(/\b(\d+\s?(?:kw|hp|ton|tonne|mm|cm|inch|kg|phase|v|volt)[a-z]*)\b/gi)
  const specs = specMatch ? [...new Set(specMatch.map((s) => s.trim()))].join(', ') : ''

  // Confidence heuristic
  let confidence = Math.min(0.5 + best.hits * 0.18, 0.98)
  if (best.hits === 0) confidence = machine ? 0.45 : 0.25

  return {
    machine: machine || 'Unspecified machine',
    category: best.key,
    quantity,
    budget,
    specs,
    confidence: Number(confidence.toFixed(2)),
  }
}

/** Build the WhatsApp message text sent to a supplier (AI-drafted RFQ). */
export function draftSupplierRFQ(enquiry, supplier) {
  return [
    `Hi ${supplier.name},`,
    ``,
    `Vision Global has a buyer requirement and you are matched for *${enquiry.category}*.`,
    ``,
    `• Machine: ${enquiry.machine}`,
    `• Quantity: ${enquiry.quantity}`,
    enquiry.specs ? `• Specs: ${enquiry.specs}` : null,
    ``,
    `Please share your best *quotation* (unit price, lead time, validity).`,
    `Reply to this WhatsApp and our system will capture it automatically.`,
    ``,
    `— Vision Global Procurement (Enquiry ${enquiry.ref})`,
  ].filter((l) => l !== null).join('\n')
}

/** Build the final message auto-sent to the buyer on approval. */
export function draftBuyerOffer(enquiry, proposal) {
  return [
    `Hello ${enquiry.buyerName},`,
    ``,
    `Thank you for your enquiry (${enquiry.ref}). Here is our offer:`,
    ``,
    `• Machine: ${enquiry.machine}`,
    `• Quantity: ${enquiry.quantity}`,
    `• Price: ${proposal.currency} ${proposal.finalPrice.toLocaleString()} (per unit)`,
    `• Lead time: ${proposal.leadTimeDays} days`,
    `• Validity: ${proposal.validityDays} days`,
    ``,
    `Kindly confirm to proceed with the order.`,
    ``,
    `— Vision Global`,
  ].join('\n')
}

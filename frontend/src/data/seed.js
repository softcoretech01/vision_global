/* Seed data loaded on first run (acts as the initial database). */

export const seedSuppliers = [
  { id: 'S-101', name: 'Precision CNC Works', whatsapp: '+91 98400 11223', email: 'sales@precisioncnc.in', categories: ['CNC & Machining'], location: 'Coimbatore', rating: 4.6, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 10 },
  { id: 'S-102', name: 'TechnoMill Systems',  whatsapp: '+91 99620 44556', email: 'rfq@technomill.com',     categories: ['CNC & Machining', 'Material Handling'], location: 'Pune', rating: 4.3, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 8 },
  { id: 'S-103', name: 'PackPro Machinery',   whatsapp: '+91 90030 77881', email: 'info@packpro.in',        categories: ['Packaging'], location: 'Ahmedabad', rating: 4.5, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 6 },
  { id: 'S-104', name: 'SealRight Automation', whatsapp: '+91 91760 22114', email: 'sales@sealright.in',     categories: ['Packaging', 'Printing'], location: 'Mumbai', rating: 4.1, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 5 },
  { id: 'S-105', name: 'FlexoPrint Tech',     whatsapp: '+91 93450 66332', email: 'quote@flexoprint.in',    categories: ['Printing'], location: 'Delhi', rating: 4.4, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 4 },
  { id: 'S-106', name: 'PolyMould Industries', whatsapp: '+91 98210 55447', email: 'sales@polymould.in',    categories: ['Plastic & Injection'], location: 'Vadodara', rating: 4.2, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 3 },
  { id: 'S-107', name: 'FoodTech Equipments', whatsapp: '+91 90470 88990', email: 'rfq@foodtecheq.in',      categories: ['Food Processing'], location: 'Chennai', rating: 4.0, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 2 },
  { id: 'S-108', name: 'WeaveWell Textile Mch', whatsapp: '+91 94430 33221', email: 'info@weavewell.in',    categories: ['Textile'], location: 'Tirupur', rating: 4.3, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 1 },
]

// Sample enquiries representing the 4 key lifecycle stages:
// 1. Buyer Enquiry Request
// 2. Supplier Enquiry Sent
// 3. Supplier Proposal Received
// 4. Buyer Proposal Sent
export const seedEnquiries = [
  {
    id: 'E-1004', ref: 'ENQ-1004',
    buyerName: 'Suresh Patel', buyerPhone: '+91 97230 44551', buyerEmail: 'suresh@patelengg.in',
    company: 'Patel Engineering Works',
    channel: 'WhatsApp',
    rawMessage: 'Need high-speed corrugation box making machine 3 ply, urgent quotation needed for plant setup in Ahmedabad.',
    machine: 'Corrugation Machine', category: 'Packaging', quantity: 1, specs: '3-ply high speed', budget: 1200000,
    confidence: 0.92,
    status: 'BUYER_ENQUIRY_REQUEST',
    createdAt: Date.now() - 1000 * 60 * 50,
    timeline: [
      { t: Date.now() - 1000 * 60 * 50, text: 'Enquiry received via WhatsApp' },
      { t: Date.now() - 1000 * 60 * 45, text: 'AI extracted: Packaging · Corrugation Machine · qty 1 (92%)' },
    ],
  },
  {
    id: 'E-1003', ref: 'ENQ-1003',
    buyerName: 'Anita Roy', buyerPhone: '+91 98310 99882', buyerEmail: 'procure@apexpharma.com',
    company: 'Apex Pharma Ltd',
    channel: 'Email',
    rawMessage: 'Looking for automatic rotary blister packing machine with 35 strokes/min. Delivery within 60 days.',
    machine: 'Blister Packing Machine', category: 'Packaging', quantity: 2, specs: 'Rotary auto, 35 strokes/min', budget: 1800000,
    confidence: 0.89,
    status: 'SUPPLIER_ENQUIRY_SENT',
    createdAt: Date.now() - 1000 * 60 * 60 * 8,
    timeline: [
      { t: Date.now() - 1000 * 60 * 60 * 8, text: 'Enquiry received via Email' },
      { t: Date.now() - 1000 * 60 * 60 * 7, text: 'AI extracted: Packaging · Blister Packing · qty 2 (89%)' },
      { t: Date.now() - 1000 * 60 * 60 * 6, text: 'RFQ auto-dispatched to 2 supplier(s) on WhatsApp' },
    ],
  },
  {
    id: 'E-1001', ref: 'ENQ-1001',
    buyerName: 'Ravi Kumar', buyerPhone: '+91 98765 43210', buyerEmail: 'ravi@buildwell.in',
    company: 'BuildWell Manufacturing',
    channel: 'WhatsApp',
    rawMessage: 'Hi, we need a CNC VMC machining center, around 2 units, 7.5 kW, 3 phase. Please share best quotation. Budget within 2500000.',
    machine: 'Vmc', category: 'CNC & Machining', quantity: 2, specs: '7.5 kW, 3 phase', budget: 2500000,
    confidence: 0.86,
    status: 'SUPPLIER_PROPOSAL_RECEIVED',
    createdAt: Date.now() - 1000 * 60 * 60 * 20,
    timeline: [
      { t: Date.now() - 1000 * 60 * 60 * 20, text: 'Enquiry received via WhatsApp' },
      { t: Date.now() - 1000 * 60 * 60 * 19, text: 'AI extracted: CNC & Machining · VMC · qty 2 (86%)' },
      { t: Date.now() - 1000 * 60 * 60 * 18, text: 'RFQ dispatched to 2 matched suppliers' },
      { t: Date.now() - 1000 * 60 * 60 * 3,  text: '2 supplier quotations received' },
    ],
  },
  {
    id: 'E-1002', ref: 'ENQ-1002',
    buyerName: 'Vikram Singh', buyerPhone: '+91 98110 33445', buyerEmail: 'vikram@singhauto.in',
    company: 'Singh Automotives',
    channel: 'WhatsApp',
    rawMessage: 'Require CNC Lathe Machine slant bed with 8-station turret, 1 unit. Need quotation with warranty.',
    machine: 'CNC Lathe Machine', category: 'CNC & Machining', quantity: 1, specs: 'Slant bed, 8-station turret', budget: 1100000,
    confidence: 0.94,
    status: 'BUYER_PROPOSAL_SENT',
    createdAt: Date.now() - 1000 * 60 * 60 * 48,
    timeline: [
      { t: Date.now() - 1000 * 60 * 60 * 48, text: 'Enquiry received via WhatsApp' },
      { t: Date.now() - 1000 * 60 * 60 * 47, text: 'AI extracted: CNC & Machining · CNC Lathe · qty 1 (94%)' },
      { t: Date.now() - 1000 * 60 * 60 * 46, text: 'RFQ dispatched to 2 matched suppliers' },
      { t: Date.now() - 1000 * 60 * 60 * 30, text: 'Supplier quotation received from Precision CNC Works' },
      { t: Date.now() - 1000 * 60 * 60 * 24, text: 'Buyer proposal PROP-1001 created · margin 15%' },
      { t: Date.now() - 1000 * 60 * 60 * 12, text: 'Proposal PROP-1001 approved by Admin' },
      { t: Date.now() - 1000 * 60 * 60 * 12, text: 'Offer auto-sent to buyer Vikram Singh via WhatsApp' },
    ],
  },
]

export const seedDispatches = [
  { id: 'D-1', enquiryId: 'E-1001', supplierId: 'S-101', channel: 'WhatsApp', status: 'responded', sentAt: Date.now() - 1000*60*60*18 },
  { id: 'D-2', enquiryId: 'E-1001', supplierId: 'S-102', channel: 'WhatsApp', status: 'responded', sentAt: Date.now() - 1000*60*60*18 },
  { id: 'D-3', enquiryId: 'E-1003', supplierId: 'S-103', channel: 'WhatsApp', status: 'sent', sentAt: Date.now() - 1000*60*60*6 },
  { id: 'D-4', enquiryId: 'E-1003', supplierId: 'S-104', channel: 'WhatsApp', status: 'sent', sentAt: Date.now() - 1000*60*60*6 },
  { id: 'D-5', enquiryId: 'E-1002', supplierId: 'S-101', channel: 'WhatsApp', status: 'responded', sentAt: Date.now() - 1000*60*60*46 },
]

export const seedSupplierProposals = [
  { id: 'SP-1', enquiryId: 'E-1001', dispatchId: 'D-1', supplierId: 'S-101', unitPrice: 1180000, currency: 'INR', leadTimeDays: 45, validityDays: 30, notes: 'Includes installation & training.', status: 'received', receivedAt: Date.now() - 1000*60*60*4 },
  { id: 'SP-2', enquiryId: 'E-1001', dispatchId: 'D-2', supplierId: 'S-102', unitPrice: 1095000, currency: 'INR', leadTimeDays: 60, validityDays: 21, notes: 'Ex-works, transport extra.', status: 'received', receivedAt: Date.now() - 1000*60*60*3 },
  { id: 'SP-3', enquiryId: 'E-1002', dispatchId: 'D-5', supplierId: 'S-101', unitPrice: 850000, currency: 'INR', leadTimeDays: 30, validityDays: 30, notes: 'Includes 1 year warranty.', status: 'received', receivedAt: Date.now() - 1000*60*60*30 },
]

export const seedBuyerProposals = [
  {
    id: 'BP-1', ref: 'PROP-1001',
    enquiryId: 'E-1002', supplierProposalId: 'SP-3', supplierId: 'S-101',
    baseCost: 850000, marginPct: 15, marginAmount: 127500, finalPrice: 977500,
    quantity: 1, currency: 'INR', leadTimeDays: 30, validityDays: 30,
    notes: 'Includes 1 year warranty and standard installation.',
    status: 'sent', approvedBy: 'Admin', createdAt: Date.now() - 1000*60*60*24, sentAt: Date.now() - 1000*60*60*12,
  },
]

export const DEFAULT_KEYWORDS = [
  'machine', 'quotation', 'quote', 'enquiry', 'rfq',
  'require', 'need', 'price', 'supply', 'purchase',
]

export function buildSeedDB() {
  return {
    suppliers: seedSuppliers,
    enquiries: seedEnquiries,
    dispatches: seedDispatches,
    supplierProposals: seedSupplierProposals,
    buyerProposals: seedBuyerProposals,
    settings: { keywords: [...DEFAULT_KEYWORDS], autoIntake: true },
    intakeLog: [],
    counters: { enq: 1005, prop: 2, intakeIdx: 0 },
  }
}

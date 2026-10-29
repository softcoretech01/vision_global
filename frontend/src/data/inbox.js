/* ===================================================================
   SIMULATED INBOUND INBOX (WhatsApp + Email)
   -------------------------------------------------------------------
   In production this is fed by the WhatsApp Business API webhook and an
   IMAP / email-inbox poller. The "Auto-fetch" feature walks this pool as
   if new messages were arriving, and the AI keyword filter decides which
   ones become enquiries (the rest are ignored as noise).
   =================================================================== */

export const INBOX = [
  {
    channel: 'WhatsApp', name: 'Anand Textiles', company: 'Anand Textiles',
    phone: '+91 90000 11111',
    text: 'Hi, we need a knitting machine, 2 units. Please share your best quotation with lead time.',
  },
  {
    channel: 'Email', name: 'Sunrise Foods', company: 'Sunrise Foods',
    email: 'purchase@sunrisefoods.in',
    text: 'We require an industrial dough mixer and a baking oven, qty 1 each. Kindly send quote.',
  },
  {
    channel: 'WhatsApp', name: 'Unknown', company: '',
    phone: '+91 80000 22222',
    text: 'Congratulations!! You have won a lucky prize. Click the link to claim now.',
  },
  {
    channel: 'Email', name: 'MetalWorks Pvt Ltd', company: 'MetalWorks',
    email: 'proc@metalworks.in',
    text: 'Need CNC lathe machine, 3 nos, 5.5 kW, 3 phase. Please send best price and delivery.',
  },
  {
    channel: 'WhatsApp', name: 'PackLine Industries', company: 'PackLine Industries',
    phone: '+91 70000 33333',
    text: 'Enquiry: automatic packaging and filling machine for 1L pouches. Quantity 1. Quote please.',
  },
  {
    channel: 'Email', name: 'Promo Weekly', company: '',
    email: 'news@promoweekly.com',
    text: 'Your weekly digest of trending stories and offers is here. Unsubscribe anytime.',
  },
  {
    channel: 'WhatsApp', name: 'FlexiPrint', company: 'FlexiPrint',
    phone: '+91 60000 44444',
    text: 'We want a flexo printing machine, 4 color. Please quote with validity.',
  },
]

export const INBOX_TOTAL = INBOX.length

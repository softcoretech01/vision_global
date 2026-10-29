"""Pull the Supplier-Proposal detail fields (Model, Machine Name, Width, Year, Quantity,
Mode, Colour, Rate Type, Rate, Price Term, Payment Term, Currency, Accessories) out of a
free-text supplier quote, so rows from email AND WhatsApp arrive pre-filled.

Labelled values win ("Year: 1998", "width in cm:210Cm", "Model - Super Excel"); a few
fields fall back to unlabelled cues (10xUsed -> qty 10, FOB, USD/$, "negotiable", a lone
19xx/20xx year, "190 cm"). Model / Machine Name snap to the master lists so the detail
form's dropdowns show them."""
import re
import json
from .db import admin_engine, q

# field -> label pattern. Order matters: specific labels before their prefixes
# ("rate type" before "rate", "model year" is a year, not a model).
LABELS = [
    ("year",           r"(?:model\s+year|mfg\.?\s*year|make\s+year|manufactur(?:ing|ed)\s+year|year\s+of\s+manufactur(?:e|ing)|yom|year)"),
    ("model",          r"model(?:\s*name)?(?!\s*year)"),
    ("width",          r"(?:reed\s+)?width(?:\s+in\s+(?:cm|mm|inch(?:es)?))?"),
    ("quantity",       r"(?:qty|quantity|no\.?\s+of\s+machines)"),
    ("mode",           r"mode"),
    ("machine_color",  r"colou?r"),
    ("rate_type",      r"rate\s*type"),
    ("rate",           r"rate(?!\s*type)"),
    ("price_term",     r"(?:price\s*terms?|delivery\s*terms?|incoterms?)"),
    ("payment_term",   r"payment(?:\s*terms?)?"),
    ("currency",       r"currency"),
    ("accessories",    r"accessor(?:y|ies)"),
]
SEP = r"\s*[:=\-]\s*"
# Values that naturally contain commas ("30% advance, balance before dispatch").
FULL_LINE = {"payment_term", "accessories"}
# Lines that are part of the quote's "machine/price" header, a greeting or a signature —
# never accessories.
SKIP_LINE_RE = re.compile(r"(?i)^\s*(?:machine\s+names?|(?:machine\s+)?prices?|hi|hello|dear|good\s+(?:morning|evening|afternoon)|greetings|"
                          r"please|kindly|the\s+(?:quotation|proposal)|proposal|quotation)\b")
SIGNATURE_RE = re.compile(r"(?i)^\s*--\s*$|^\s*(?:regards|thanks|thank\s+you|best|warm\s+regards|sent\s+from)\b|@|\+?\d[\d\s\-]{9,}$")

CURRENCY_CUES = [
    ("INR", r"₹|\binr\b|\brs\.?\s*\d|\brupees?\b"),
    ("USD", r"\$|\busd\b|\bdollars?\b"),
    ("EUR", r"€|\beur\b|\beuros?\b"),
    ("GBP", r"£|\bgbp\b|\bpounds?\b"),
    ("CNY", r"\bcny\b|\brmb\b|\byuan\b"),
]
PRICE_TERM_CUES = [
    ("Ex-works", r"\bex[\s\-]*works?\b|\bexw\b"),
    ("FOB", r"\bfob\b"),
    ("CIF", r"\bcif\b"),
    ("C&F", r"\bc\s*&\s*f\b|\bcnf\b|\bcfr\b"),
    ("Delivered", r"\bdelivered\b|\bdoor\s+delivery\b|\bddp\b"),
]
RATE_TYPE_CUES = [
    ("Negotiable", r"(?<!non[\s\-])\bnegotiable\b"),
    ("Fixed", r"\bfixed\s+(?:price|rate)\b|\bnon[\s\-]negotiable\b|\bfinal\s+price\b"),
    ("Per unit", r"\bper\s+(?:unit|piece|pc|machine|set)\b"),
    ("Lot", r"\b(?:as\s+a|whole|full|complete)\s+lot\b|\blot\s+price\b"),
]
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
WIDTH_RE = re.compile(r"(?i)\b(\d{2,3}(?:\.\d+)?)\s*(cm|mm)\b")
QTY_RES = [re.compile(r"(?i)(?:^|\s)(\d{1,3})\s*x\s*(?=[a-z])"),
           re.compile(r"(?i)\b(\d{1,3})\s*(?:nos?\.?|sets?|units?|pcs|pieces|machines)\b")]
PRICE_LINE_RE = re.compile(r"(?im)^.*\b(?:machine\s+)?prices?\b.*$")


def _masters(tbl):
    try:
        names = [(r.get("name") or "").strip() for r in q(admin_engine, f"SELECT name FROM {tbl} WHERE active=1")]
    except Exception:
        return []
    return sorted({n for n in names if len(n) >= 3}, key=len, reverse=True)


def masters():
    """(model names, machine names) from the masters, longest first — load once per batch."""
    return _masters("models"), _masters("machines")


def _cue(text, cues):
    for value, pat in cues:
        if re.search(pat, text, re.I):
            return value
    return None


def _key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _snap(value, options):
    """Match a typed value onto a master/option list, ignoring case, spaces and
    punctuation ("Sulzer project ile" -> "Sulzer Projectile", "OpenEnd" -> "Open End")."""
    v = _key(value)
    if not v:
        return None
    for o in options:
        if _key(o) == v:
            return o
    return None


def _labelled(text):
    """{field: value} for every 'Label: value' found (first occurrence wins). A value
    ends at a comma, semicolon or line end, so inline lists like
    'model: Super Excel, year:1998, width in cm:210Cm' split cleanly."""
    out = {}
    for field, lab in LABELS:
        stop = r"[^\n]+" if field in FULL_LINE else r"[^,;\n]+"
        m = re.search(rf"(?im)(?<![a-z]){lab}{SEP}({stop})", text)
        if m and m.group(1).strip():
            out[field] = m.group(1).strip()[:160]
    return out


def _accessories(text, labelled_value, skip_terms=()):
    """Explicit 'Accessories:' value plus the lines that follow it; otherwise the
    unlabelled spec lines of the quote (e.g. '20 Shafts', 'Staubli 2688 Dobby',
    'Frame:12'), stopping at the signature."""
    lines = text.splitlines()
    label_re = re.compile(rf"(?i)^\s*{dict(LABELS)['accessories']}{SEP}")
    keyed = re.compile(r"(?i)(?<![a-z])(?:" + "|".join(lab for _f, lab in LABELS) + rf"){SEP}")
    picked = []
    if labelled_value:
        start = next((i for i, ln in enumerate(lines) if label_re.search(ln)), None)
        if start is not None:
            # The whole rest of the line (accessory lists are comma-separated).
            picked.extend(x.strip() for x in label_re.sub("", lines[start]).split(",") if x.strip())
            for ln in lines[start + 1:]:
                if not ln.strip() or SIGNATURE_RE.search(ln) or keyed.search(ln):
                    break
                picked.append(ln.strip())
            return "\n".join(picked)[:2000]
    for ln in lines[1:]:                       # line 0 names the machine itself
        s = ln.strip()
        if not s:
            continue
        if SIGNATURE_RE.search(s):
            break
        if SKIP_LINE_RE.search(s) or keyed.search(s) or len(s) > 80:
            continue
        if any(t and t.lower() in s.lower() for t in skip_terms):   # the machine's own line
            continue
        if _cue(s, PRICE_TERM_CUES) or _cue(s, RATE_TYPE_CUES):    # "FOB Chennai" is a term, not a part
            continue
        if re.search(r"(?i)\bmachine\s*\d+\s*(?:image|photo|pic)s?\b|^this\s+(?:is\s+)?machine\b", s):
            continue
        picked.append(s)
        if len(picked) >= 12:
            break
    return "\n".join(picked)[:2000]


def parse_details(block: str, whole: str = "", known_models=None, known_machines=None) -> dict:
    """Detail fields for one machine. `block` is the part of the message about this
    machine; `whole` is the full message, used for message-wide terms (currency,
    price/payment term, rate type) the block doesn't repeat."""
    from .intake import _find_known_machines   # lazy: intake imports this module
    whole = whole or block
    known_models = _masters("models") if known_models is None else known_models
    known_machines = _masters("machines") if known_machines is None else known_machines
    lab = _labelled(block)
    lab_whole = _labelled(whole)
    out = {}

    # Model / Machine Name -> master names (what the detail-form dropdowns list).
    model = _snap(lab.get("model"), known_models)
    if not model:
        hits = _find_known_machines(block, known_models)
        model = hits[0] if hits else lab.get("model")
    if model:
        out["model"] = model
    mach = _find_known_machines(block, known_machines)
    if mach:
        out["machine_name"] = mach[0]

    # Unlabelled cues are read with price lines removed, so "Price: 2000" isn't a year.
    cues_text = PRICE_LINE_RE.sub("", block)
    if lab.get("year"):
        y = YEAR_RE.search(lab["year"])
        out["year"] = y.group(1) if y else lab["year"][:16]
    else:
        years = set(YEAR_RE.findall(cues_text))
        if len(years) == 1:
            out["year"] = years.pop()
    if lab.get("width"):
        out["width"] = lab["width"][:80]
    else:
        widths = WIDTH_RE.findall(cues_text)
        if len(widths) == 1:
            out["width"] = f"{widths[0][0]} {widths[0][1].lower()}"
    if lab.get("quantity"):
        out["quantity"] = lab["quantity"][:40]
    else:
        for rx in QTY_RES:
            m = rx.search(cues_text)
            if m:
                out["quantity"] = m.group(1)
                break
    for f in ("mode", "machine_color", "rate"):
        if lab.get(f):
            out[f] = lab[f][:80]

    # Message-wide terms: labelled value snapped to the form's options, else a cue.
    def term(field, cues, limit):
        raw = lab.get(field) or lab_whole.get(field)
        val = (_cue(raw, cues) or raw) if raw else (_cue(block, cues) or _cue(whole, cues))
        if val:
            out[field] = val[:limit]
    term("currency", CURRENCY_CUES, 40)
    term("price_term", PRICE_TERM_CUES, 80)
    term("rate_type", RATE_TYPE_CUES, 40)
    pay = lab.get("payment_term") or lab_whole.get("payment_term")
    if pay:
        out["payment_term"] = pay[:120]

    acc = _accessories(block, lab.get("accessories"), (out.get("model"), out.get("machine_name")))
    if acc:
        out["accessories"] = acc
    return out


def split_blocks(text: str, machines: list) -> list:
    """The slice of `text` about each machine, so per-machine specs don't bleed across
    rows. When the machines aren't on separate lines (e.g. one 'Machine names: A, B'
    line), every machine gets the whole text."""
    low = (text or "").lower()
    starts, pos = [], 0
    for m in machines:
        i = low.find((m or "").lower(), pos)
        if i < 0:
            return [text] * len(machines)
        starts.append(low.rfind("\n", 0, i) + 1)   # start of that line
        pos = i + len(m)
    if len(set(starts)) < len(starts):
        return [text] * len(machines)
    return [text[s:(starts[k + 1] if k + 1 < len(starts) else len(text))] for k, s in enumerate(starts)]


# Fields a supplier is asked for when their quote leaves them out, with the wording
# used in the WhatsApp request. Edit this list to change what counts as "complete".
REQUIRED = [
    ("price", "Price"),
    ("model", "Model"),
    ("year", "Year of manufacture"),
    ("width", "Width"),
    ("quantity", "Quantity"),
    ("price_term", "Price term (Ex-works / FOB / CIF)"),
]


def missing_fields(row: dict) -> list:
    """Labels of the required details (and photos) this proposal row still lacks."""
    out = [label for f, label in REQUIRED if row.get(f) in (None, "", 0)]
    photos = row.get("photos")
    if isinstance(photos, str):
        try:
            photos = json.loads(photos)
        except Exception:
            photos = []
    if not photos:
        out.append("Photos of the machine")
    return out

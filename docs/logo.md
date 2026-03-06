# Logo

## Concept

**mongotic** bridges two worlds: MongoDB's flexible document model and
SQLAlchemy v2's composable, Pythonic query API. The logo should capture
this idea of *connection* — something that feels simultaneously familiar to
Python ORM developers and native to the document-database space.

The name "mongotic" echoes words like *hypnotic* and *robotic* — precise,
rhythmic, automatic. The logo should feel calm and confident, not flashy.

---

## Symbol / Icon

**Primary concept: the leaf-bracket.**

MongoDB is traditionally represented by a stylised leaf. SQLAlchemy queries
are built with parentheses — `select(User).where(...)`. The icon fuses both:

- A **single, clean leaf** shape (tall, pointed, slightly asymmetric — echoing
  MongoDB's own leaf, but redrawn to feel independent).
- The left edge of the leaf doubles as an **opening parenthesis** `(` — so the
  silhouette reads as both *organic* (document, leaf) and *structural*
  (code, query, bracket).
- Inside the leaf, a very subtle **three-line horizontal rule** (reminiscent of
  a document's field rows, or a database table) rendered in a lighter tint of
  the primary colour.

The icon should work at 16 × 16 px (favicon) and at 512 × 512 px without
losing legibility.

---

## Colour Palette

| Role | Name | Hex |
|------|------|-----|
| Primary | Mongo Green | `#00C853` |
| Accent | Query Blue | `#1565C0` |
| Dark background | Deep Navy | `#0D1B2A` |
| Light background | Off-white | `#F5F7FA` |
| Neutral | Slate | `#546E7A` |

**Usage guidance:**

- On dark backgrounds (README, PyPI badge): green icon + white wordmark.
- On light backgrounds (docs site): green icon + deep navy wordmark.
- The accent blue appears only in the three-line document rule inside the leaf,
  and optionally in hover states on the docs site.

---

## Typography

- **Wordmark font:** [Inter](https://rsms.me/inter/) — Semi-Bold (600) weight.
  Clean, modern, highly legible at small sizes. Freely licensed.
- **Casing:** all lowercase — `mongotic`. The lowercase reinforces the
  Pythonic, approachable personality (compare: `pip install mongotic`).
- **Spacing:** generous letter-spacing (~0.04 em) between `mongo` and `tic`
  is optional; the split can be visually hinted with a slightly bolder `t` or
  a hairline colour shift to `#00C853` on the `tic` syllable.
- **Fallback stack:** `Inter, system-ui, sans-serif`

---

## Composition

```
  [leaf-bracket icon]   mongotic
```

- Icon sits to the left of the wordmark, vertically centred.
- Icon height = cap-height of the wordmark (so they visually align).
- Minimum clear space around the lockup: 1× icon width on all sides.

**Icon-only variant** (for favicons, GitHub avatar, PyPI project icon):
the leaf-bracket alone, on a deep navy `#0D1B2A` square with 10 % padding.

---

## Mood & References

- **Calm, structural, minimal** — not playful, not corporate.
- Closest references: Pydantic's clean mark, Typer/FastAPI's icon simplicity,
  the restraint of the Go gopher's environment logos.
- Avoid: gradients, drop shadows, 3-D effects, skeuomorphism.

---

## Deliverables Checklist (for designer)

- [ ] SVG lockup (icon + wordmark) — light variant
- [ ] SVG lockup (icon + wordmark) — dark variant
- [ ] SVG icon only — square format (`logo-icon.svg`)
- [ ] PNG icon 512 × 512 px (`logo-icon-512.png`)
- [ ] PNG icon 32 × 32 px (`favicon.png`)
- [ ] PyPI badge-sized PNG 200 × 60 px (`logo-badge.png`)

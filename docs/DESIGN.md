# Design

Heart Line's interface is built on the KUEC Attar design system (`kuec-attar/docs/DESIGN.md`, `STYLE_RULES.md`, `client/tailwind.config.js`), adapted for this product. Everything lives in one file, `web/src/styles.css`. When you add or change a reusable pattern, update this document in the same change.

## Character

A calm clinical tool. Trustworthy before impressive: this is medical information, and visual confidence must never outrun what the data supports. Quiet by default, so the one colour means something.

## What was kept from Attar

| Rule | In Heart Line |
| --- | --- |
| Grey ground, solid white cards, no card borders, no shadows | `html` is `--g-100`; `.card`, `.next`, `details.fold` are white |
| A box inside a card is a grey fill, never a border | `.card .notice`, `.chain-item`, `.done-note`, `.error`, `.phone .slot` |
| Every corner is 4px | `--r: 4px`. One exception: the phone frame in the staff preview, which depicts a device |
| One family per script, three weights | Manrope, and IBM Plex Sans Arabic under `dir="rtl"`; 400, 500, 700 |
| A closed type scale | 12, 14, 16, 18, 24, 30, and 48 for one display figure |
| The header is the dark ink field; the current page has a 2px bar under it | `.top`, `.nav a.on` |
| Anything selected is underlined, never boxed | `.tabs button.on`; no pills, no segmented track |
| No separator lines; space does the job | Tables have no row rules; sections are separate cards |
| No tinted backgrounds | Statuses are plain words in ink (`.pill`, `.band`) |
| No eyebrows, no accent bars, no all-caps labels | None exist |
| Buttons answer the press | `transform: scale(0.97)` on `:active`, 160ms, strong ease-out |
| Hover only where the pointer is real, and only on rows that are links | `@media (hover: hover) and (pointer: fine)`, `tr.link` |
| Focus is always visible | 2px ring in the action colour with a 2px gap |
| Arabic uses the same sizes and weights, looser line height, no tracking | `[dir="rtl"]` rules |
| Skeletons are flat grey with a slow pulse | `.skeleton` |

## What was adapted

| Attar | Heart Line | Why |
| --- | --- | --- |
| Leaf green is the action colour; red is for errors only | Red (`--red-600`, `#9f1239`) is the action colour: primary buttons, links, the selected bar, key figures | The owner asked to keep Heart Line's red. With red taken, errors are a grey box with a bold title, not a second red |
| Ink is a green-cast near-black | Ink is a warm near-black (`--ink-900`, `#1c1517`) | So the ink sits with the red the way Attar's sits with green |
| Levels are a coloured dot beside an ink word | Levels and statuses are words only; the strongest band is bold | Heart Line's house rule is no coloured dots |
| Categorical colour is allowed in charts and the knowledge graph | Colour fills are allowed in the family tree and the charts | Same principle: colour only where it carries data |
| Tailwind classes and a check script | Plain CSS with tokens on `:root` | Heart Line has one stylesheet and no Tailwind; a check script is a follow-up |

## Tokens

All on `:root` in `web/src/styles.css`.

- Ground: `--g-50` to `--g-500`, neutral greys. The page is `--g-100`.
- Ink: `--ink-900` body and headings, `--ink-700` secondary, `--ink-600` muted, `--ink-500` the lightest text allowed.
- Action: `--red-600` resting, `--red-700` hover, `--red-800` pressed.
- Data: `--s-index`, `--s-confirmed`, `--s-invited`, `--s-wellchild`, `--s-negative`, `--s-unknown`, `--s-deceased`. Family tree and charts only.
- Motion: `--ease-out`, `--dur-press` (160ms), `--dur-ui` (200ms). Never `transition: all`, never ease-in.

## Type roles

| Role | Size and weight | Where |
| --- | --- | --- |
| Page title | 30 bold | `h1`, one per page |
| Section heading | 24 bold | `h2`, card titles that start a section |
| Card or panel title | 18 bold | `h3`, fold summaries |
| Lead | 18 regular | `.lede`, the one sentence under a page title |
| Body | 16 regular | Running text, table cells, fields |
| Label | 14 medium | Navigation, tabs, table headings, small buttons |
| Secondary | 14 regular | `.small`, helper text, meta lines |
| Caption | 12 medium | The "New result" marker, chart labels |

## Patterns specific to Heart Line

- **Role home is a queue.** Tabs are counts; each row says why it is there (`web/src/screens/Home.tsx`).
- **One next step per case.** The server decides the title, the sentence and the buttons (`machine.next_step`, `machine.possible`); the page only draws them (`NextStep` in `Patient.tsx`).
- **Confirm before anything is sent.** The coordinator sees every recipient and the exact message before sending.
- **The standard score and the product's score are separate, labelled blocks.** DLCN is "the standard clinical score"; the model is "added by this tool".
- **A band in words, not a percentage.** The exact figure is in Score details.
- **Reasons for and against.** Red bars point towards FH, grey bars away from it.
- **The relative's page stands alone.** No staff navigation, Arabic first for Arabic speakers, all copy in `web/src/locale/`.
- **Demo controls stay in the demo bar.** No screen copy tells the reader to press a demo button.

## Not done

- No `check:design` script enforces these rules yet.
- No design system page renders the tokens.
- The staff interface is English only.

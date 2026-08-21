# Dikte UI Master Visual Reference — "Warm Technical Minimalism"

> Bu dosya, Dikte arayüzünün yeniden inşası için ana görsel referans prompt'unun
> kalıcı kopyasıdır (2026-08-21). Tam orijinal metin aşağıdadır.

---

Create an exceptionally polished **desktop application UI design reference for Dikte**, a fast local-first voice dictation, transcription, cleanup and productivity utility.

This image will be used as the **MASTER VISUAL REFERENCE** for rebuilding the entire application's interface.

It must therefore communicate a complete, consistent design language through:

* window architecture
* navigation
* typography
* spacing
* buttons
* dropdowns
* text inputs
* password/API-key fields
* toggles
* checkboxes
* status indicators
* cards
* separators
* tooltips
* provider selectors
* model selectors
* keyboard shortcut fields
* loading/status states
* iconography
* focus states
* hierarchy
* color usage

The final result should look like a **real production desktop application designed by an experienced product design team**, not a speculative concept and absolutely not an "AI dashboard".

---

# PRODUCT PERSONALITY

Dikte is a background desktop utility.

Its personality should feel:

quiet
fast
precise
trustworthy
local-first
technical without looking developer-only
professional
tactile
mature
understated
high quality
easy to scan
native to a desktop computer

Imagine the visual discipline of:

premium productivity software
professional audio utilities
high-end computer hardware configuration software
modern European industrial design
Swiss information design
Braun-like functional restraint
carefully designed Windows productivity software

Use those references **only as principles**.

DO NOT copy an existing application.

Dikte must have its own identity.

---

# CRITICAL STYLE DIRECTION

Call the design language:

**WARM TECHNICAL MINIMALISM**

The application should combine:

warm natural neutrals
precise software geometry
restrained industrial-design details
excellent typography
small amounts of character
dense but calm information architecture

Avoid the generic 2024–2026 AI SaaS aesthetic.

The interface must NOT communicate:

artificial intelligence
chatbot
futurism
crypto
Web3
gaming
cyberpunk
startup landing page
generic SaaS dashboard

There should be absolutely:

NO purple gradients
NO blue-purple gradients
NO neon
NO glowing borders
NO aurora backgrounds
NO glassmorphism
NO excessive blur
NO floating translucent cards
NO AI sparkle icons
NO stars
NO robot iconography
NO brain graphics
NO neural-network graphics
NO magic wand imagery
NO holographic surfaces
NO glossy 3D buttons
NO enormous pill-shaped controls
NO excessively rounded cards
NO excessive shadows

The design should still look beautiful when every decorative effect is removed.

Typography, proportions, spacing and hierarchy should create the beauty.

---

# PRIMARY COLOR SYSTEM

Build the interface around this warm palette.

### Canvas / application background

Warm stone: **#F4F1EA**

Not pure white. Slightly warm and comfortable without appearing beige or vintage.

### Sidebar background

Warm sand: **#EEE9DE**

Subtle separation from the main content area.

### Primary elevated surface

Soft ivory: **#FBFAF6**

Grouped settings surfaces and important input areas.

### Secondary surface

Soft warm gray: **#F1EEE6**

Hover backgrounds, subtle rows, secondary controls.

### Primary text

Ink charcoal: **#242628**

Deep charcoal instead of absolute black.

### Secondary text

Muted graphite: **#686D69**

### Tertiary / helper text

Muted stone: **#8A8E89**

### Borders

Warm neutral border: **#D8D2C6** (1 px)

### Stronger border

**#C7C1B5** — focused or more prominent containers.

---

# BRAND ACCENTS

## Terracotta — **#E4573D**

Primary recording / voice activity color. Use VERY selectively: recording, active
voice capture, important action, small brand moments. Do not make every button
orange. Recording status may use a tiny terracotta dot.

## Muted sage — **#A7B8AA**

Selected sidebar backgrounds, subtle active states, soft status backgrounds,
selected chips, gentle focus accents.

Dark readable sage: **#597064** — links, selected text, small icons.

---

# SEMANTIC COLORS

Success: **#4F805F** / bg **#E6EFE7**
Warning: **#A67836** / bg **#F4EBD9**
Error: **#B85247** / bg **#F5E4E1**
Recording: **#E4573D**

Do not rely on color alone. Always accompany with text or a simple icon.

---

# TYPOGRAPHY

Preferred: **Segoe UI Variable / Inter**.

- Page title: 24–26 px semibold
- Section heading: 15–16 px semibold
- Body: 14 px / ~20 px line height
- Control labels: 13–14 px
- Secondary explanations: 12–13 px
- Small metadata: 11–12 px
- Button text: 13–14 px medium

Sentence case everywhere. Avoid ALL CAPS. Monospaced only for model IDs, API
URLs, keyboard shortcuts, file paths.

---

# SPACING SYSTEM

4 px base grid: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40.

- Main content horizontal padding: **32 px**
- Large section separation: **32 px**
- Card internal padding: **20–24 px**
- Related control spacing: **8–12 px**
- Label-to-control spacing: **8 px**

Professional desktop density — noticeably denser than mobile or marketing sites.

---

# SHAPE LANGUAGE

- Small control: 4–5 px
- Button: 6 px
- Input/dropdown: 6 px
- Settings card: 8 px
- Popover/dialog: 10–12 px max

Avoid huge 16–24 px SaaS card radii.

---

# WINDOW ARCHITECTURE

One complete Dikte desktop window, 16:10 (~1440×900 scene), window ~1180×760 px.
Direct desktop screenshot look. Platform-neutral (PyQt6, Windows/Linux).
NO macOS traffic lights, no laptop mockup, no hands, no browser chrome.

---

# NAVIGATION ARCHITECTURE

Vertical settings sidebar, ~210–220 px, background #EEE9DE.

Top-left: small Dikte symbol (three tiny rounded vertical bars: short, tall,
medium) + wordmark **Dikte**, muted label **Settings**.

Sections: General, API & Models, Cleanup Rules, Agent, Meeting, Minutes,
Audio File, Shortcuts, History.

Icons: 16–18 px outline, muted charcoal-gray, no color. Selected section:
**API & Models** — soft muted sage-tinted background, 6 px radius, calm.

Sidebar bottom: **Dikte 1.x** + tiny status row (sage dot, **Ready**).

---

# MAIN CONTENT — API & MODELS

Subtitle: **Choose where transcription and cleanup run.**

Compact secondary action near title: **Check connections**.
Strong primary action far right: **Save changes** — ink charcoal primary button
(bg #242628, text #FBFAF6), NOT orange. Button height 36–38 px.

## Section 1 — Providers

Supporting text: **Credentials are stored on this device.**

One large settings surface (not floating cards). Provider rows: OpenAI,
OpenRouter, Deepgram. Each row: provider name, status indicator, masked API key
input (~36 px), small **Test** button (secondary: ivory bg, 1 px warm border).

Configured example: `••••••••••••••••••••••sk-R7d9` + sage dot + **Connected**.
Unconfigured: muted circle + **Not configured**. Faint internal dividers between
rows. No colorful provider logos.

## Section 2 — Speech to text

Subtitle: **Turn recordings into text.**

Compact two-column form:

- Provider: `[ Deepgram ▾ ]`
- Model: `[ nova-3 ▾ ] [ Fetch models ]`
- Language: `[ Automatic ▾ ]`

Status row: sage dot **Model ready**, secondary text **Fetched 18 models**.
Understated dark-sage link: **Use a local model instead**.

## Section 3 — Transcript cleanup

Subtitle: **Improve punctuation and obvious transcription mistakes.**

Compact toggle ON (muted sage track) at section's upper-right.

Rows: Provider `[ OpenRouter ▾ ]`, Model `[ anthropic/claude-sonnet… ▾ ] [ Fetch
models ]`, Thinking `[ Off ▾ ]`.

Info note (small info icon): **Cleanup runs after transcription and does not
change the original recording.** Slightly tinted warm-neutral surface, no blue box.

---

# COMPONENT STYLE

Inputs/dropdowns: bg #FBFAF6, 1 px #D8D2C6 border, 6 px radius, 36–38 px height,
12 px horizontal padding. Focus: stronger border + subtle sage focus ring (no
glow). Dropdown arrow: small simple chevron.

Buttons — three levels:

- PRIMARY: charcoal bg, ivory text (**Save changes**)
- SECONDARY: ivory bg, warm gray border, charcoal text (**Fetch models**, **Test**)
- GHOST: transparent, dark sage or charcoal text (**Use local model**, **Reset**)

Danger buttons muted red only for actually destructive actions.

Toggles: ~34×18 px; inactive warm gray track, active muted sage track, small
circular thumb.

Checkboxes: small squares, ≤5 px radius, charcoal or dark sage fill, white check.

Status language: subtle — ● Connected, ● Ready, ● Local, ● Downloading,
● Needs key. Chips: small height, soft tint, 6 px radius.

Iconography: thin-to-medium outline family, 16–18 px, 1.5–1.75 px stroke,
slightly rounded endpoints. No filled/3D/AI sparkle icons.

---

# UNIQUE DIKTE BRAND DETAIL

**Three tiny rounded vertical bars** (short, tall, medium) — spoken-audio motif.
Use sparingly: Dikte logo, recording status, empty audio state. Terracotta
appears primarily in the tiny recording indicator within this symbol.

---

# SURFACES AND DEPTH

Mostly FLAT. Subtle 1 px borders, very small tonal differences, extremely
restrained shadows (max `0 1px 2px rgba(20,20,18,0.04)`; many containers none).
No paper texture, no skeuomorphism. Hierarchy via spacing and tone first.

Sidebar #EEE9DE / canvas #F4F1EA / surfaces #FBFAF6.

---

# INFORMATION DENSITY

Compact, efficient, scan-friendly. ~65–70% of main content area contains useful
controls. Professional desktop preferences panel, not mobile settings.

---

# QUALITY TARGET

Must look like "a screenshot from the latest production build of Dikte" — crisp
text, mathematically clean alignment, realistic control dimensions, implementable
with PyQt6. No charts, no fake analytics, no dashboard graphs.

---

# ABSOLUTE NEGATIVE DIRECTION

No purple/violet, electric blue primary, neon cyan, AI gradients, glowing edges,
glass cards, glassmorphism, frosted panels, aurora, 3D icons, sparkles, stars,
robots, brains, neural nets, chat-bubble identity, magic wands, oversized
illustration, marketing hero, statistics cards, graphs, charts, fake analytics,
crypto/gaming/cyberpunk UI, RGB lighting, giant rounded rectangles, excessive
pills, extreme shadows, pure #000000 / #FFFFFF, random gradients, mobile
proportions, macOS traffic lights, browser chrome, device mockups.

---

# FINAL COMPOSITION

One polished **Dikte Settings — API & Models** screen: left navigation, warm
sand sidebar, warm stone canvas, ivory surfaces, ink-charcoal typography, muted
sage interaction states, terracotta only as the recording accent, crisp Segoe UI
Variable / Inter typography, compact controls, precise spacing, subtle 1 px
borders, restrained 6–8 px radii.

The feeling: **a beautifully engineered physical audio tool translated into
desktop software.** Modern, calm, highly usable, distinctive and timeless.

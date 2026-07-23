# CLI Picker UX Notes (plan-level, no code yet)

Requirement: given the list of MEGA download entries parsed from a pahe.ink page (see
`docs/research/site-structure.md`), let the user pick one via arrow keys **or** typed number
input, then hand the chosen entry's gate URL off to Part 2.

## Options considered

### 1. `questionary`
- Built on `prompt_toolkit`. Very popular, actively maintained, good docs.
- Native `questionary.select(...)` gives arrow-key navigation + Enter out of the box, and
  supports a `use_shortcuts=True`/instruction mode where pressing a number jumps directly to
  that item (via `questionary.select(..., use_indicator=True)` plus shortcut keys `1-9`).
  Typed multi-digit numbers beyond 1-9 aren't natively supported by the shortcut mode, but
  for a picker over a modest list (a handful of resolutions/episodes) single-digit shortcuts
  are normally enough.
- Pros: pleasant default styling, easy API, cross-platform (works on Windows via
  `prompt_toolkit`), well-suited for exactly this "pick one of a short list" use case.
- Cons: pulls in `prompt_toolkit` as a fairly heavy dependency; numeric jump is limited to
  single-digit shortcuts without extra wiring.

### 2. `InquirerPy`
- Also `prompt_toolkit`-based; a more actively-styled "Inquirer.js-like" alternative to the
  older/unmaintained `PyInquirer`.
- Very similar capability set to `questionary` (arrow-key list, fuzzy list, checkbox, etc.).
  Slightly more configurable/verbose API; larger feature surface than this project needs.
- Pros/cons largely mirror `questionary`. No decisive advantage for this simple use case.

### 3. `simple-term-menu`
- Lightweight, minimal-dependency (pure Python + terminal escape codes), no
  `prompt_toolkit`.
- Gives arrow-key + Enter navigation and also lets you type digits to jump to an entry
  (`show_search_hint`/index typing is supported reasonably well for numbered lists).
- Cons: **Unix/Linux/macOS only — no Windows support** (relies on POSIX terminal APIs). If
  cross-platform is a requirement (unclear — user's OS wasn't specified beyond "this
  machine" which is Linux), this is a real limitation to flag.
- Pros: very small, fast, no heavy dependency tree — good fit if this stays Linux-only.

### 4. Hand-rolled `curses` (or `readchar` + manual redraw)
- Full control over exact behavior (arrow keys, direct numeric input of arbitrary length
  with a fallback "press Enter to confirm the typed number" flow, custom highlighting of
  MEGA-only entries grouped by resolution/episode, etc.).
- Cons: most implementation and maintenance effort of all options; `curses` is POSIX-only
  (no native Windows support without `windows-curses`); more edge cases to get right
  (terminal resize, non-interactive/piped stdin fallback, etc.) that the libraries above
  already handle.
- Only worth it if the pickers above turn out to be insufficiently customizable (e.g. if we
  want a genuinely fluid "type any number of digits to filter/select" input alongside arrow
  keys, or a two-level picker showing resolution → entry in one interactive view).

## Recommendation

**Use `questionary`.** Reasoning:
- The picker needs to satisfy two lightweight requirements (arrow keys, numeric input) over
  a short list (typically well under 20 entries: a handful of resolutions/episodes × a
  handful of grouped MEGA entries) — this is squarely `questionary`'s sweet spot and its
  single-digit shortcut mode covers "typed number input" well enough in practice for lists
  this size.
- It's the most widely adopted of the `prompt_toolkit`-based options for exactly this
  "pick-one-from-a-list" CLI pattern, meaning good community support/answers if something
  goes wrong.
- Cross-platform, in case this tool is ever run somewhere other than this Linux machine.
- Avoid `simple-term-menu`'s Windows gap and avoid hand-rolling `curses` unless a concrete
  UX need (not yet identified) demands it.

If, once building, arbitrary multi-digit numeric jump turns out to matter more than
currently expected (e.g. dozens of episodes), fall back to a plain non-interactive numbered
list + `input()` (typed number, no arrow keys) as a secondary/`--no-fancy-ui` mode — cheap to
add alongside `questionary` and useful for non-TTY/CI/piped usage anyway, where
`prompt_toolkit`-style interactive pickers don't work at all.

## Data flow: "selected item → resolved MEGA link"

Plan-level shape (no code):

1. Part 1 parses the page into a flat list of entries, each carrying at minimum:
   `{ resolution_or_quality_label, group_label (e.g. "Per Episode"/"Batch"/"Episode 3"),
     provider_text ("MG"/"MG 1"/...), gate_url }`.
2. Filter to `provider_text` matching the MEGA pattern for this phase.
3. Build picker choices as `f"{resolution_or_quality_label} — {group_label}"` (human label)
   → value = the entry's `gate_url` (not yet a mega.nz link — see Part 2 findings: the real
   host is hidden behind a gate that could not be fully traced yet).
4. Picker returns the chosen entry's `gate_url`.
5. That `gate_url` is the **input** to Part 2 (the redirect-resolution step), which — once
   implemented per `docs/research/mega-link-redirect-flow.md`'s recommendation
   (Playwright, hard timeout, domain allowlist) — outputs the final `https://mega.nz/...`
   URL string. Keep this as a clean function boundary
   (`resolve_gate_url(gate_url: str) -> str`) so Part 1 (parsing/picking) and Part 2
   (redirect-following) stay independently testable — Part 1 can be fully tested/demoed
   today without Part 2 existing at all, by just printing the chosen `gate_url`.

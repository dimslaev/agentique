# Redesign feed + rest of app to match the homepage

## Context
The homepage got its own "wire/terminal" look on a prior branch: an
ink/paper/wire/dim/signal palette, Archivo display + IBM Plex Mono/Sans, zero
border radius, hairline borders instead of cards. It was scoped to `.landing`
only, so every other page (feed, profile, developers, admin, auth pages) kept
the original generic shadcn theme. The app read as two different products
glued together — this makes the rest of the visible app match the homepage.

## Approach
Instead of hand-restyling every component, repoint shadcn's semantic tokens
(`--background`, `--foreground`, `--border`, `--primary`, `--muted-foreground`,
…) at the same `--ink/--paper/--wire/--dim/--signal` variables the homepage
already defines. Since virtually every component (Button, Card, Input, Dialog,
Tabs, Table, Sidebar) is built on those tokens, the whole app re-themes at
once, in both light and dark mode. Then fix the handful of spots that
hardcode a color/radius instead of using a token, and do bespoke content
passes (feed rows, tabs) so it matches homepage patterns, not just its palette.

### 1. Global tokens & type — `frontend/src/index.css`
Added semantic remaps in `:root` referencing `--ink/--paper/--wire/--dim/
--signal` (background/foreground, card/popover, primary=signal, secondary/
muted/accent=wire, border/input=wire, ring=signal, sidebar*). `.dark` already
redeclares those five landing vars, so derived tokens flip automatically — no
duplicate `.dark` block needed. `--radius` set to `0rem`, which feeds the
`--radius-sm/md/lg/xl` keys Tailwind's `rounded-*` utilities read, so most
components square off without their own edits. Body font set to
`var(--font-body)`.

### 2. Hardcoded spots that don't inherit from tokens
`rounded-full` is a literal size, not on the `--radius` scale:
- `ui/button.tsx`, `ui/badge.tsx`: pill → `rounded-none`.
- `Articles/LikeButton.tsx`: `text-orange-500`/`fill-orange-500` → `text-primary`/`fill-primary`.

### 3. Feed rows → homepage's row language
Extracted `ScoreRail` (+ score constants) out of `Home/TopicLane.tsx` into
shared `Articles/ScoreRail.tsx`. `ArticleRow.tsx` rewritten to use it plus the
same `font-wire uppercase` meta line and square hairline tag/category chips.
`ArticlesList.tsx` gained a slim header echoing `TopicLanes`' legend bar.
`TopicLane.tsx` now imports the shared rail. testids and query logic
untouched.

### 4. Profile tabs → underline wire tabs
`ui/tabs.tsx` (only consumed by `profile.tsx`) restyled from pill/segmented
control to a flat `border-b` strip with `font-wire uppercase` triggers.

### 5. Headings & labels
`font-display` on page h1s (Profile, Admin, Developers, Newsletter, auth
pages) and section headings (UserSettings). `font-wire` on eyebrow labels
(FilterSectionLabel, Footer stats, Sidebar nav index badges, Developers
"Response"/mono bits). Logo wordmark switched from `font-mono` to
`font-display` to match the landing header.

### 6. Developers page
`EndpointCard`/`CodeBlock` flatten automatically via tokens; added
`font-wire` to method/path/param bits and `font-display` to "Pro plan".

## Scope / non-goals
- Admin and Newsletter get the token/radius/font treatment for free, no
  bespoke content rewrite (internal-only / unused respectively).
- No new dependencies — Archivo/IBM Plex Mono/Sans already imported.
- `--destructive` and `--chart-*` left alone.

## Verification
- Dev server: click through Feed, Profile (all 4 tabs), Developers, Admin,
  Login/Signup, in light + dark.
- `bunx playwright test` — existing specs don't assert on classnames/colors.
- `bun run lint` (biome).

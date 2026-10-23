# 18. Frontend in FSD layers, routes as pages

## Status

Accepted. Amends 3.

## Context

The frontend grew as `components/<Area>/`, `hooks/`, `context/` and `lib/`,
with PascalCase files beside kebab-case shadcn files. Nothing said what could
import what. The rails imported helpers out of `components/Articles/`, and
Articles imported the rails' like button back. The layout route held two
providers that only the feed read.

The backend already has layers with one rule (ADR 17): entry composes
features, features use core, imports point down. The frontend had no
matching vocabulary.

## Decision

    routes/     TanStack's file routes: one file per page, composes the rest
    widgets/    rails/ header/ footer/       blocks that compose features
    features/   feed/ sign-in/ account/ analytics/ developer-api/
    shared/     ui/ lib/ auth/ api/          no domain, used by everything

- **Feature-Sliced Design, with `routes/` in place of `pages/`.** TanStack
  already maps one file to one page. A `pages/` layer would mirror
  `routes/` file for file. Routes stay thin: they compose widgets and
  features and hold the route's own config.
- **No `entities/`.** The generated client in `shared/api` already holds the
  domain types. An `entities/article` would only re-export `ArticlePublic`.
- **Imports point down, and slices on one layer never import each other.**
  This matches ADR 17's rule for backend features. When two features need
  one thing, it moves to `shared/`. That is why `FilterOption`, the score
  band, the published window and the origin options sit in `shared/`.
- **A slice is reached through its `index.ts`.** Inside a slice, imports are
  relative. A slice is split into `ui/`, `model/`, `lib/` and `config/`
  segments.
- **The like button lives in `features/feed`.** `ArticleRow` renders it, and
  `ArticleRow` is the feed's. A separate `like-article` feature would be a
  feature importing a feature.
- **The sign-in pages' frame is a route.** `routes/_auth.tsx` is a pathless
  layout with the header and footer widgets. It cannot sit in `shared/`
  because it renders widgets.
- **The rails keep their state in a zustand store in `widgets/rails`.** No
  provider wraps the layout. `RailsLayout` marks the rails present, and the
  layout's header reads one selector to span them.
- **The feed's filters live in the feed route.** Only the feed reads them, so
  they reset when the reader leaves it.
- **Files are kebab-case.** Exported names stay PascalCase or camelCase. The
  vendored shadcn files already were.
- **`shared/` keeps its name.** FSD names the layer `shared`, and Steiger
  only knows it by that name. ADR 3 is amended to allow it and still checks
  every name below it.

## Enforcement

- `bun run lint:layers` runs Steiger with the FSD plugin in the
  test-frontend workflow. It fails on a cross-slice or upward import and on
  a slice or `shared` segment without a public API.
- `fsd/insignificant-slice` is off. Steiger counts references from FSD
  layers only, and `routes/` is not one, so every slice a route imports
  would read as unused.
- Steiger does not check `routes/`, since it is not a layer. Biome's
  `noRestrictedImports` covers that gap. It fails lint on an import of
  `@/features/<x>/...` or `@/widgets/<x>/...` that goes past the slice's
  `index.ts`.
- Biome's `useFilenamingConvention` fails on a file name that is not
  kebab-case. TanStack's `__root.tsx`, `_layout.tsx` and `$param.tsx` pass
  as they are.
- The vendored shadcn files in `shared/ui` are excluded from Biome by name,
  so a file added there later is linted unless it is added to that list.

## Consequences

The frontend now has the backend's shape: layers whose imports point down,
and one folder per feature. An import that breaks the layers fails CI
rather than review.

A helper two slices need moves to `shared/` first, in its own change.

Folder names are not checked. Biome's rule reads file names, and Steiger
does not check case.

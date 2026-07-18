# Publisher & Tag sidebar filters

Add publisher + tag filtering to the article sidebar. Both single-select
(like `kind`). Top-N shown as chips, long tail via searchable combobox
backed by server typeahead.

## Decisions

- Tags single-select (reuse existing single `tag` backend param)
- Publisher single-select (new backend param)
- Overflow UI: shadcn Combobox (add `cmdk` + `@radix-ui/react-popover`)
- Top-N source: new `/articles/facets` endpoint
- Combobox search: server-side typeahead endpoints

## Backend

**1. `publisher` param on `read_articles`** (`articles.py`) — mirror `tag` block:
- `Article.publisher_id in (select Publisher.id where slug == publisher)`

**2. `GET /articles/facets`** — top publishers + tags by article count
- publishers: group Article by publisher_id, join Publisher, count, order desc, limit ~8
- tags: join ArticleTag -> Tag, group, count, order desc, limit ~8
- response: `{ publishers: [{slug,name,count}], tags: [{slug,name,count}] }`
- new `FacetsPublic` model; v1 ignores since/category (cacheable)

**3. Typeahead endpoints** for combobox search
- `GET /articles/publishers?q=&limit=` -> `[{slug,name,count}]` (ilike name, order by count)
- `GET /articles/tags?q=&limit=` -> `[{slug,name,count}]`

**4. Regen client** — `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`, commit.

## Frontend

**5. Filters context** — add `publisher: string`, `tag: string` (default "").
- wire into `ArticlesList` queryKey + `readArticles({ publisher, tag })`
- note: search mode still bypasses filters (existing behavior)

**6. shadcn Combobox** — install `cmdk` + `@radix-ui/react-popover`,
add stock `ui/command.tsx` + `ui/popover.tsx` (no custom logic).

**7. `FacetFilter` component** (reused for publisher + tag)
- `useQuery(['facets'])` for top-N chips, long `staleTime`
- top-N rendered in existing `FilterGroup` dot-button style (matches look)
- "More…" trigger opens Combobox popover
  - `useQuery(['publisher-search', q])` debounced typeahead
  - selecting sets the filter; selected value shows as active chip even if
    not in top-N (inject it)
- clear/"All" option resets to ""

**8. Place in `Filters.tsx`** below Kind. Publisher first, then Tags.

## Risk notes

- Selected item outside top-N: must render it as active chip (inject into list)
- Debounce typeahead (~250ms), min 1 char, `keepPreviousData`
- Combobox is stock shadcn source -> low bug surface
- Facets/typeahead need indexes on publisher_id + article_tag for speed at scale

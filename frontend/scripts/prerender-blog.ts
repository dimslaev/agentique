/**
 * Blog SSG: validates content/blog/*.md against the content contract and
 * renders static HTML into dist/blog/ (one folder per post + an index).
 *
 * Runs after `vite build` (see "build" in package.json) so it can link the
 * hashed CSS bundle from dist/assets/ — the same stylesheet the SPA ships.
 * Any contract violation exits non-zero and fails the build; this is the
 * mechanical validation gate for agent-written posts (PR review is the
 * editorial one). The contract lives in .agents/blog-writer.md.
 *
 * Run standalone: bun scripts/prerender-blog.ts (needs an existing dist/).
 */

import fs from "node:fs"
import path from "node:path"
import { marked } from "marked"
import YAML from "yaml"

const FRONTEND_ROOT = path.resolve(import.meta.dirname, "..")
const CONTENT_DIR = path.join(FRONTEND_ROOT, "content", "blog")
const DIST_DIR = path.join(FRONTEND_ROOT, "dist")
const SITE_URL = process.env.SITE_URL ?? "https://agentique.ch"
const API_URL = process.env.VITE_API_URL ?? "https://api.agentique.ch"
const SITE_NAME = "agentique"

const SLUG_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const MIN_BODY_WORDS = 150
// The rendered <title> appends " · agentique" (12 chars) — keep the total
// title tag within Google's ~60-70 char display budget.
const MAX_TITLE_CHARS = 55
const MAX_DESCRIPTION_CHARS = 160

type Post = {
  file: string
  slug: string
  title: string
  description: string
  topic: string
  date: string
  articles: string[]
  bodyMd: string
}

const errors: string[] = []

function fail(file: string, msg: string) {
  errors.push(`${file}: ${msg}`)
}

function parsePost(file: string, raw: string): Post | null {
  if (!raw.startsWith("---\n")) {
    fail(file, "missing frontmatter (file must start with ---)")
    return null
  }
  const end = raw.indexOf("\n---\n", 4)
  if (end === -1) {
    fail(file, "unterminated frontmatter")
    return null
  }

  let fm: Record<string, unknown>
  try {
    fm = YAML.parse(raw.slice(4, end))
  } catch (e) {
    fail(file, `frontmatter is not valid YAML: ${e}`)
    return null
  }

  const bodyMd = raw.slice(end + 5).trim()
  const str = (key: string): string =>
    typeof fm[key] === "string" ? (fm[key] as string).trim() : ""

  const post: Post = {
    file,
    slug: str("slug"),
    title: str("title"),
    description: str("description"),
    topic: str("topic"),
    date: typeof fm.date === "string" ? fm.date : String(fm.date ?? ""),
    articles: Array.isArray(fm.articles) ? fm.articles.map(String) : [],
    bodyMd,
  }

  validatePost(post)
  return post
}

function validatePost(p: Post) {
  const { file } = p

  if (!p.title) fail(file, "missing title")
  else if (p.title.length > MAX_TITLE_CHARS)
    fail(file, `title is ${p.title.length} chars (max ${MAX_TITLE_CHARS})`)

  if (!p.description) fail(file, "missing description")
  else if (p.description.length > MAX_DESCRIPTION_CHARS)
    fail(
      file,
      `description is ${p.description.length} chars (max ${MAX_DESCRIPTION_CHARS})`,
    )

  if (!SLUG_RE.test(p.slug)) fail(file, `invalid slug "${p.slug}"`)
  if (!SLUG_RE.test(p.topic)) fail(file, `invalid topic "${p.topic}"`)

  if (!DATE_RE.test(p.date) || Number.isNaN(Date.parse(p.date))) {
    fail(file, `invalid date "${p.date}" (expected YYYY-MM-DD)`)
  } else {
    const today = new Date().toISOString().slice(0, 10)
    if (p.date > today) fail(file, `date ${p.date} is in the future`)
    const expected = `${p.date}-${p.slug}.md`
    if (path.basename(file) !== expected)
      fail(file, `filename must be ${expected} (date-slug)`)
  }

  if (p.articles.length === 0) fail(file, "articles list is empty")
  for (const url of p.articles) {
    if (!/^https?:\/\//.test(url)) fail(file, `article is not a URL: ${url}`)
  }
  if (new Set(p.articles).size !== p.articles.length)
    fail(file, "articles list has duplicates")

  const words = p.bodyMd.split(/\s+/).filter(Boolean).length
  if (words < MIN_BODY_WORDS)
    fail(file, `body is ${words} words (min ${MIN_BODY_WORDS})`)

  // Every external link in the body must be a cited article — the guard
  // against hallucinated URLs. Site-relative links (/, /blog/...) are fine.
  const cited = new Set(p.articles)
  const linkRe = /\]\((https?:\/\/[^)\s]+)\)|<(https?:\/\/[^>\s]+)>/g
  for (const m of p.bodyMd.matchAll(linkRe)) {
    const url = m[1] ?? m[2]
    if (url.startsWith(SITE_URL)) continue
    if (!cited.has(url)) fail(file, `body links uncited URL: ${url}`)
  }
}

// ─── HTML rendering ──────────────────────────────────────────────────────────

// Mirrors the SPA's ThemeProvider (storageKey "vite-ui-theme", default
// "system") so static pages come up in the theme the app last set.
const THEME_SCRIPT = `try{var t=localStorage.getItem("vite-ui-theme");if(t==="dark"||((!t||t==="system")&&matchMedia("(prefers-color-scheme: dark)").matches))document.documentElement.classList.add("dark")}catch(e){}`

// Static pages never load the SPA router, so lib/analytics.ts's onResolved
// hook never fires here — this beacon posts to the same endpoint, using the
// same visitor_id localStorage key, so blog pageviews land in analytics_event
// alongside SPA ones.
const ANALYTICS_SCRIPT = `try{var k="analytics_visitor_id";var id=localStorage.getItem(k);if(!id){id=crypto.randomUUID();localStorage.setItem(k,id)}fetch("${API_URL}/api/v1/analytics/collect",{method:"POST",headers:{"Content-Type":"application/json"},keepalive:true,body:JSON.stringify({event:"pageview",path:location.pathname,referrer:document.referrer||undefined,visitor_id:id})}).catch(function(){})}catch(e){}`

function esc(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
}

function shell(opts: {
  title: string
  description: string
  canonicalPath: string
  cssHrefs: string[]
  ogType: "article" | "website"
  publishedDate?: string
  body: string
}): string {
  const canonical = `${SITE_URL}${opts.canonicalPath}`
  const css = opts.cssHrefs
    .map((href) => `<link rel="stylesheet" href="${href}">`)
    .join("\n    ")
  const published = opts.publishedDate
    ? `\n    <meta property="article:published_time" content="${opts.publishedDate}">`
    : ""
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${esc(opts.title)} · ${SITE_NAME}</title>
    <meta name="description" content="${esc(opts.description)}">
    <link rel="canonical" href="${canonical}">
    <meta property="og:title" content="${esc(opts.title)}">
    <meta property="og:description" content="${esc(opts.description)}">
    <meta property="og:type" content="${opts.ogType}">
    <meta property="og:url" content="${canonical}">${published}
    <meta name="twitter:card" content="summary">
    <script>${THEME_SCRIPT}</script>
    <script>${ANALYTICS_SCRIPT}</script>
    ${css}
  </head>
  <body class="min-h-screen bg-background text-foreground antialiased">
    <header class="border-b">
      <div class="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
        <a href="/" class="inline-flex h-8 items-center font-mono font-medium lowercase text-foreground">${SITE_NAME}</a>
        <nav class="flex items-center gap-4 font-mono text-[11px] text-muted-foreground">
          <a href="/blog/" class="hover:text-foreground">blog</a>
          <a href="/" class="hover:text-foreground">feed</a>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-3xl px-4 py-10">
${opts.body}
    </main>
    <footer class="border-t">
      <div class="mx-auto max-w-3xl px-4 py-4 font-mono text-[11px] text-muted-foreground">
        Curated by <a href="/" class="underline hover:text-foreground">${SITE_NAME}</a> — AI news, deduped, scored and tagged daily.
      </div>
    </footer>
  </body>
</html>
`
}

function renderPost(p: Post, cssHrefs: string[]): string {
  const bodyHtml = marked.parse(p.bodyMd, { async: false })
  const body = `      <article>
        <p class="font-mono text-[11px] text-muted-foreground"><time datetime="${p.date}">${p.date}</time> · ${esc(p.topic)}</p>
        <h1 class="mt-2 text-3xl font-semibold tracking-tight">${esc(p.title)}</h1>
        <div class="prose mt-8 max-w-none">
${bodyHtml}
        </div>
      </article>
      <p class="mt-10 border-t pt-6 font-mono text-[11px] text-muted-foreground">
        Sourced from ${p.articles.length} curated articles — <a href="/" class="underline hover:text-foreground">browse the live feed</a>.
      </p>`
  return shell({
    title: p.title,
    description: p.description,
    canonicalPath: `/blog/${p.slug}/`,
    cssHrefs,
    ogType: "article",
    publishedDate: p.date,
    body,
  })
}

// Real, indexable SPA routes — auth-gated pages (login, settings, admin,
// items, profile) are deliberately excluded, nothing there for Google to rank.
const STATIC_ROUTES = ["/", "/developers", "/newsletter"]

function renderSitemap(posts: Post[]): string {
  const today = new Date().toISOString().slice(0, 10)
  const urls = [
    ...STATIC_ROUTES.map((route) => ({ loc: route, lastmod: today })),
    { loc: "/blog/", lastmod: posts[0]?.date ?? today },
    ...posts.map((p) => ({ loc: `/blog/${p.slug}/`, lastmod: p.date })),
  ]
  const entries = urls
    .map(
      (u) => `  <url>
    <loc>${SITE_URL}${u.loc}</loc>
    <lastmod>${u.lastmod}</lastmod>
  </url>`,
    )
    .join("\n")
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${entries}
</urlset>
`
}

function renderIndex(posts: Post[], cssHrefs: string[]): string {
  const items = posts
    .map(
      (p) => `        <li class="border-b py-6 first:pt-0">
          <p class="font-mono text-[11px] text-muted-foreground"><time datetime="${p.date}">${p.date}</time> · ${esc(p.topic)}</p>
          <h2 class="mt-1 text-xl font-semibold tracking-tight"><a href="/blog/${p.slug}/" class="hover:underline">${esc(p.title)}</a></h2>
          <p class="mt-2 text-sm text-muted-foreground">${esc(p.description)}</p>
        </li>`,
    )
    .join("\n")
  const body = `      <h1 class="text-3xl font-semibold tracking-tight">Blog</h1>
      <p class="mt-3 text-muted-foreground">Topic roundups written from the ${SITE_NAME} feed.</p>
      <ul class="mt-8 list-none">
${items || '        <li class="py-6 text-muted-foreground">No posts yet.</li>'}
      </ul>`
  return shell({
    title: "Blog",
    description: `Topic roundups of curated AI news from the ${SITE_NAME} feed.`,
    canonicalPath: "/blog/",
    cssHrefs,
    ogType: "website",
    body,
  })
}

// ─── Main ────────────────────────────────────────────────────────────────────

function main() {
  const assetsDir = path.join(DIST_DIR, "assets")
  if (!fs.existsSync(assetsDir)) {
    console.error(
      "prerender-blog: dist/assets not found — run `vite build` first",
    )
    process.exit(1)
  }
  const cssHrefs = fs
    .readdirSync(assetsDir)
    .filter((f) => f.endsWith(".css"))
    .map((f) => `/assets/${f}`)

  const files = fs.existsSync(CONTENT_DIR)
    ? fs.readdirSync(CONTENT_DIR).filter((f) => f.endsWith(".md"))
    : []

  const posts: Post[] = []
  for (const file of files.sort()) {
    const raw = fs.readFileSync(path.join(CONTENT_DIR, file), "utf-8")
    const post = parsePost(file, raw)
    if (post) posts.push(post)
  }

  const seen = new Set<string>()
  for (const p of posts) {
    if (seen.has(p.slug)) fail(p.file, `duplicate slug "${p.slug}"`)
    seen.add(p.slug)
  }

  if (errors.length > 0) {
    console.error("prerender-blog: content contract violations:")
    for (const e of errors) console.error(`  - ${e}`)
    process.exit(1)
  }

  posts.sort((a, b) => b.date.localeCompare(a.date))

  for (const p of posts) {
    const dir = path.join(DIST_DIR, "blog", p.slug)
    fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(path.join(dir, "index.html"), renderPost(p, cssHrefs))
  }
  fs.mkdirSync(path.join(DIST_DIR, "blog"), { recursive: true })
  fs.writeFileSync(
    path.join(DIST_DIR, "blog", "index.html"),
    renderIndex(posts, cssHrefs),
  )
  fs.writeFileSync(path.join(DIST_DIR, "sitemap.xml"), renderSitemap(posts))

  console.log(`prerender-blog: rendered ${posts.length} post(s) + index`)
}

main()

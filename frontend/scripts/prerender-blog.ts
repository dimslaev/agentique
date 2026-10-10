/**
 * Blog SSG: renders content/blog/*.md into static HTML in dist/blog/ (one
 * folder per post, an index) and writes dist/sitemap.xml.
 *
 * Runs after `vite build` (see "build" in package.json) so it can link the
 * hashed CSS bundle from dist/assets/, the same stylesheet the SPA ships.
 * Tailwind scans this file for class names (`@source` in src/index.css), so a
 * class added to a template here only exists after the next `vite build`.
 *
 * The checks here are structural only (see blog-posts.ts): frontmatter parses,
 * title/description/topic present, filename is YYYY-MM-DD-slug.md, date not in
 * the future, slugs unique. Any violation exits non-zero and fails the build.
 * The content rules for an issue live in backend/app/newsletter/broadcast.py
 * (draft_issue refuses a post that breaks them); the writing guide is
 * .claude/skills/newsletter/SKILL.md; the PR is the editorial review.
 *
 * Run standalone: bun scripts/prerender-blog.ts (needs an existing dist/).
 * Preview: bun scripts/prerender-blog.ts --watch re-renders dist/blog/ on every
 * change in content/blog/ and serves dist/ on http://localhost:4174 (PORT to
 * change it). Run one `vite build` first for dist/assets/.
 */

import fs from "node:fs"
import http from "node:http"
import path from "node:path"
import { Marked, type Tokens } from "marked"
import {
  bundledLanguages,
  createHighlighter,
  type HighlighterGeneric,
  type LanguageRegistration,
} from "shiki"
import { CONTENT_DIR, loadPosts, type PostMeta } from "./blog-posts"

const FRONTEND_ROOT = path.resolve(import.meta.dirname, "..")
const DIST_DIR = path.join(FRONTEND_ROOT, "dist")
const SITE_URL = process.env.SITE_URL ?? "https://agentique.ch"
const API_URL = process.env.VITE_API_URL ?? "https://api.agentique.ch"
const SITE_NAME = "agentique"
const SHIKI_THEME = "vitesse-dark"
const MORE_ISSUES = 3

// ─── Code highlighting ───────────────────────────────────────────────────────

// Shiki ships no BAML grammar; this covers what the posts show: keywords,
// strings, #"block"# prompts with their {{ }} / {% %} template tags,
// @@attributes, comments and type names.
const BAML: LanguageRegistration = {
  name: "baml",
  scopeName: "source.baml",
  patterns: [
    { include: "#comment" },
    { include: "#block-string" },
    { include: "#string" },
    {
      match:
        "\\b(function|class|enum|client|test|generator|template_string|retry_policy)\\b(?:<\\w+>)?\\s+(\\w+)",
      captures: {
        1: { name: "keyword.control.baml" },
        2: { name: "entity.name.function.baml" },
      },
    },
    {
      match: "^\\s*(\\w+)(?=\\s)",
      captures: { 1: { name: "variable.other.property.baml" } },
    },
    { match: "@@?\\w+", name: "keyword.control.baml" },
    { match: "\\b[A-Z]\\w*\\b", name: "entity.name.type.baml" },
    { match: "[{}\\[\\]()<>,]|->", name: "punctuation.baml" },
  ],
  repository: {
    comment: { match: "//.*$", name: "comment.line.baml" },
    string: { begin: '"', end: '"', name: "string.quoted.double.baml" },
    "block-string": {
      begin: '#"',
      end: '"#',
      name: "string.quoted.block.baml",
      patterns: [{ include: "#template" }],
    },
    template: {
      begin: "\\{[{%]",
      end: "[}%]\\}",
      name: "meta.embedded.template.baml",
      beginCaptures: { 0: { name: "punctuation.baml" } },
      endCaptures: { 0: { name: "punctuation.baml" } },
      patterns: [{ include: "#string" }],
    },
  },
}

type Highlighter = HighlighterGeneric<string, string>

function codeLangs(posts: PostMeta[]): string[] {
  const langs = new Set<string>()
  const marked = new Marked()
  for (const p of posts)
    marked.walkTokens(marked.lexer(p.bodyMd), (t) => {
      if (t.type === "code" && t.lang) langs.add(t.lang.split(/\s/)[0])
    })
  return [...langs]
}

function shikiLang(lang: string, highlighter: Highlighter): string {
  return highlighter.getLoadedLanguages().includes(lang) ? lang : "text"
}

async function loadHighlighter(posts: PostMeta[]): Promise<Highlighter> {
  const bundled = codeLangs(posts).filter((l) => l in bundledLanguages)
  return (await createHighlighter({
    themes: [SHIKI_THEME],
    langs: [...bundled, BAML],
  })) as Highlighter
}

// ─── Markdown to HTML ────────────────────────────────────────────────────────

const A_PROSE =
  "text-paper underline decoration-signal decoration-[1.5px] underline-offset-4 hover:text-signal"
const P_PROSE = "mb-[1.3em]"
const H2_PROSE =
  "mt-[1.8em] mb-[0.6em] font-display text-[28px] font-bold leading-[1.2] tracking-[-0.02em] text-paper"
const H3_PROSE =
  "mt-[1.8em] mb-[0.6em] font-display text-[21px] font-semibold leading-[1.3] tracking-[-0.01em] text-paper"
const CODE_PROSE =
  "border border-wire bg-[#22251a] px-1.5 py-0.5 font-wire text-[0.86em] text-paper"
const FIGURE_PROSE = "mb-[1.5em] border border-wire bg-[#1a1c13]"
const FIGCAPTION_PROSE =
  "border-b border-wire px-4 py-2 font-wire text-[11px] uppercase tracking-[0.08em] text-dim"
const PRE_PROSE =
  "m-0 overflow-x-auto px-5 py-[18px] font-wire text-[14px] leading-[1.65]"
const LIST_PROSE = "mb-[1.3em] list-none p-0"
const LI_PROSE = "mb-[0.35em] flex gap-[14px]"
const UL_MARK = "mt-[0.72em] h-1.5 w-1.5 flex-none bg-signal"
const OL_MARK =
  "w-6 flex-none font-wire text-[14px] leading-[1.72rem] text-signal"
const BLOCKQUOTE_PROSE =
  "mb-[1.5em] border-l-2 border-wire py-1 pl-[22px] text-[20px] italic leading-[1.6] text-[#a9ab95] [&>p:last-child]:mb-0"
const HR_PROSE = "my-10 h-px border-0 bg-wire"
const END_MARK = "ml-2.5 inline-block h-[9px] w-[9px] bg-signal align-[1px]"

function esc(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
}

function markdown(highlighter: Highlighter): Marked {
  return new Marked({
    renderer: {
      paragraph({ tokens }) {
        return `<p class="${P_PROSE}">${this.parser.parseInline(tokens)}</p>\n`
      },
      heading({ tokens, depth }) {
        const tag = depth <= 2 ? "h2" : "h3"
        const cls = depth <= 2 ? H2_PROSE : H3_PROSE
        return `<${tag} class="${cls}">${this.parser.parseInline(tokens)}</${tag}>\n`
      },
      link({ href, title, tokens }) {
        const t = title ? ` title="${esc(title)}"` : ""
        return `<a href="${esc(href)}"${t} class="${A_PROSE}">${this.parser.parseInline(tokens)}</a>`
      },
      strong({ tokens }) {
        return `<strong class="font-semibold text-paper">${this.parser.parseInline(tokens)}</strong>`
      },
      codespan({ text }) {
        return `<code class="${CODE_PROSE}">${esc(text)}</code>`
      },
      code({ text, lang }) {
        const name = (lang ?? "").split(/\s/)[0] || "text"
        const html = highlighter.codeToHtml(text, {
          lang: shikiLang(name, highlighter),
          theme: SHIKI_THEME,
          transformers: [
            {
              pre(node) {
                // Drop the theme's background: the figure carries the surface.
                node.properties.style = "color:#dbd7ca"
                node.properties.class = `shiki ${PRE_PROSE}`
              },
            },
          ],
        })
        return `<figure class="${FIGURE_PROSE}"><figcaption class="${FIGCAPTION_PROSE}">${esc(name)}</figcaption>${html}</figure>\n`
      },
      list(token: Tokens.List) {
        const start = Number(token.start) || 1
        const items = token.items
          .map((item, i) => {
            const mark = token.ordered
              ? `<span class="${OL_MARK}">${start + i}.</span>`
              : `<span aria-hidden="true" class="${UL_MARK}"></span>`
            const body = this.parser.parse(item.tokens)
            return `<li class="${LI_PROSE}">${mark}<div class="min-w-0 [&>p:last-child]:mb-0">${body}</div></li>`
          })
          .join("\n")
        const tag = token.ordered ? "ol" : "ul"
        return `<${tag} class="${LIST_PROSE}">\n${items}\n</${tag}>\n`
      },
      blockquote({ tokens }) {
        return `<blockquote class="${BLOCKQUOTE_PROSE}">${this.parser.parse(tokens)}</blockquote>\n`
      },
      hr() {
        return `<hr class="${HR_PROSE}">\n`
      },
    },
  })
}

function renderBody(p: PostMeta, md: Marked): string {
  const html = md.parse(p.bodyMd, { async: false }).trimEnd()
  // The accent square closes the essay, when it ends on a paragraph.
  const last = html.lastIndexOf("</p>")
  if (last === -1 || last !== html.length - 4) return html
  return `${html.slice(0, last)}<span aria-hidden="true" class="${END_MARK}"></span></p>`
}

// ─── Page parts ──────────────────────────────────────────────────────────────

// Static pages never load the SPA router, so lib/analytics.ts's onResolved
// hook never fires here. This beacon posts to the same endpoint, using the
// same visitor_id localStorage key, so blog pageviews land in analytics_event
// alongside SPA ones.
const ANALYTICS_SCRIPT = `try{var k="analytics_visitor_id";var id=localStorage.getItem(k);if(!id){id=crypto.randomUUID();localStorage.setItem(k,id)}fetch("${API_URL}/api/v1/analytics/collect",{method:"POST",headers:{"Content-Type":"application/json"},keepalive:true,body:JSON.stringify({event:"pageview",path:location.pathname,referrer:document.referrer||undefined,visitor_id:id})}).catch(function(){})}catch(e){}`

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
]

function dateParts(date: string): { day: number; month: string; year: string } {
  const [year, month, day] = date.split("-")
  return { day: Number(day), month: MONTHS[Number(month) - 1], year }
}

// "27 Jul 2026"
function longDate(date: string): string {
  const d = dateParts(date)
  return `${d.day} ${d.month.slice(0, 3)} ${d.year}`
}

// "Jul 27"
function shortDate(date: string): string {
  const d = dateParts(date)
  return `${d.month.slice(0, 3)} ${d.day}`
}

// "July 2026"
function monthLabel(date: string): string {
  const d = dateParts(date)
  return `${d.month} ${d.year}`
}

function postHref(p: PostMeta): string {
  return `/blog/${p.slug}/`
}

function sources(p: PostMeta) {
  return p.links.filter((l) => !l.url.startsWith(SITE_URL))
}

const ARROW_RIGHT =
  '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 7h11M8 3l4 4-4 4"/></svg>'
const ARROW_LEFT =
  '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 7H2M6 3L2 7l4 4"/></svg>'

const META = "font-wire text-[11px] uppercase tracking-[0.08em] text-dim"
const SECTION_HEAD =
  "flex items-baseline justify-between border-b border-wire pb-3 font-wire text-[11px] uppercase tracking-[0.12em] text-dim"
const NAV_LINK = "inline-flex h-11 items-center hover:text-paper"

function header(current: "index" | "post"): string {
  const aria = current === "index" ? ' aria-current="page"' : ""
  return `    <header class="border-b border-wire bg-ink">
      <div class="mx-auto flex h-12 max-w-[768px] items-center gap-4 px-4">
        <a href="/" class="inline-flex h-11 items-center font-display text-[17px] font-extrabold tracking-[-0.01em] text-paper hover:text-paper">${SITE_NAME}</a>
        <nav aria-label="Site" class="ml-auto flex items-center gap-5 font-wire text-[11px] uppercase tracking-[0.08em]">
          <a href="/" class="${NAV_LINK} text-dim">Feed</a>
          <a href="/blog/"${aria} class="${NAV_LINK} text-paper shadow-[inset_0_-2px_0_var(--signal)]">Blog</a>
        </nav>
      </div>
    </header>`
}

const FOOTER = `    <footer class="border-t border-wire">
      <div class="mx-auto flex max-w-[768px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-5 font-wire text-[11px] text-dim">
        <span>${SITE_NAME} · AI news, deduped, scored and tagged daily</span>
        <a href="/" class="ml-auto inline-flex min-h-11 items-center text-paper hover:text-signal">Browse the feed →</a>
      </div>
    </footer>`

function shell(opts: {
  title: string
  description: string
  canonicalPath: string
  cssHrefs: string[]
  ogType: "article" | "website"
  publishedDate?: string
  jsonLd?: object
  current: "index" | "post"
  main: string
}): string {
  const canonical = `${SITE_URL}${opts.canonicalPath}`
  const css = opts.cssHrefs
    .map((href) => `<link rel="stylesheet" href="${href}">`)
    .join("\n    ")
  const published = opts.publishedDate
    ? `\n    <meta property="article:published_time" content="${opts.publishedDate}">`
    : ""
  // "<" escaped so a title can never close the script element.
  const jsonLd = opts.jsonLd
    ? `\n    <script type="application/ld+json">${JSON.stringify(opts.jsonLd).replaceAll("<", "\\u003c")}</script>`
    : ""
  return `<!doctype html>
<html lang="en" class="dark">
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
    <link rel="icon" type="image/x-icon" href="/assets/images/favicon.png">${jsonLd}
    <script>${ANALYTICS_SCRIPT}</script>
    ${css}
  </head>
  <body class="flex min-h-screen flex-col bg-ink font-body text-[#cfccbd] antialiased">
${header(opts.current)}
${opts.main}
${FOOTER}
  </body>
</html>
`
}

// ─── Pages ───────────────────────────────────────────────────────────────────

function renderPost(
  p: PostMeta,
  all: PostMeta[],
  md: Marked,
  cssHrefs: string[],
): string {
  const cited = sources(p)
  const sourceItems = cited
    .map(
      (
        s,
        i,
      ) => `          <li class="grid grid-cols-[36px_minmax(0,1fr)] gap-x-3 border-b border-[#262920] py-3">
            <span class="pt-0.5 font-wire text-[12px] tabular-nums text-signal">${String(i + 1).padStart(2, "0")}</span>
            <span class="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
              <a href="${esc(s.url)}" class="text-[15px] leading-[1.45] text-paper [overflow-wrap:anywhere] hover:text-signal">${esc(s.text)}</a>
              <span class="font-wire text-[11px] text-dim">${esc(s.domain)}</span>
            </span>
          </li>`,
    )
    .join("\n")
  const sourcesSection = cited.length
    ? `
      <section aria-labelledby="sources" class="mt-16 border-t border-wire pt-5">
        <h2 id="sources" class="font-wire text-[11px] uppercase tracking-[0.12em] text-paper">Sources · ${cited.length}</h2>
        <ol class="mt-3 list-none p-0">
${sourceItems}
        </ol>
      </section>`
    : ""

  const more = all.filter((o) => o.slug !== p.slug).slice(0, MORE_ISSUES)
  const moreItems = more
    .map(
      (
        m,
      ) => `          <li class="grid grid-cols-[64px_minmax(0,1fr)] gap-x-5 border-b border-wire py-[18px]">
            <time datetime="${m.date}" class="pt-1 font-wire text-[12px] uppercase tracking-[0.04em] tabular-nums text-dim">${shortDate(m.date)}</time>
            <span class="flex min-w-0 flex-col gap-1.5">
              <a href="${postHref(m)}" class="font-display text-[18px] font-semibold leading-[1.3] tracking-[-0.01em] text-paper hover:text-signal">${esc(m.title)}</a>
              <span class="font-wire text-[11px] text-dim">#${esc(m.topic)}</span>
            </span>
          </li>`,
    )
    .join("\n")
  const moreSection = more.length
    ? `
      <section aria-labelledby="more" class="mt-16">
        <div class="${SECTION_HEAD}">
          <h2 id="more" class="text-paper">More issues</h2>
          <a href="/blog/" class="inline-flex min-h-8 items-center hover:text-paper">All ${all.length} →</a>
        </div>
        <ul class="list-none p-0">
${moreItems}
        </ul>
      </section>`
    : ""

  const main = `    <main class="mx-auto box-border w-full max-w-[712px] flex-1 px-4 pt-8 pb-[88px]">
      <a href="/blog/" class="inline-flex min-h-11 items-center gap-2 ${META} hover:text-paper">${ARROW_LEFT}All issues</a>
      <article>
        <header class="mt-6">
          <p class="flex flex-wrap items-center gap-x-[18px] gap-y-1.5 ${META}">
            <time datetime="${p.date}">${longDate(p.date)}</time>
            <span class="normal-case tracking-[0.02em] text-signal">#${esc(p.topic)}</span>
            <span>${p.readingMinutes} min read</span>${cited.length ? `\n            <span>${cited.length} sources</span>` : ""}
          </p>
          <h1 class="mt-5 font-display text-[clamp(34px,5.4vw,50px)] font-extrabold leading-[1.05] tracking-[-0.03em] text-paper">${esc(p.title)}</h1>
          <p class="mt-5 text-[19px] leading-[1.55] text-[#a9ab95]">${esc(p.description)}</p>
        </header>
        <hr class="${HR_PROSE}">
        <div class="text-[18px] leading-[1.72] text-[#cfccbd]">
${renderBody(p, md)}
        </div>
      </article>${sourcesSection}${moreSection}
    </main>`

  return shell({
    title: p.title,
    description: p.description,
    canonicalPath: postHref(p),
    cssHrefs,
    ogType: "article",
    publishedDate: p.date,
    jsonLd: {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: p.title,
      description: p.description,
      datePublished: p.date,
      url: `${SITE_URL}${postHref(p)}`,
      mainEntityOfPage: `${SITE_URL}${postHref(p)}`,
      publisher: { "@type": "Organization", name: SITE_NAME, url: SITE_URL },
    },
    current: "post",
    main,
  })
}

function renderIndex(posts: PostMeta[], cssHrefs: string[]): string {
  const [latest, ...rest] = posts
  const latestBlock = latest
    ? `
      <a href="${postHref(latest)}" class="mt-14 block border border-wire bg-[#1a1c13] p-5 text-[#cfccbd] hover:border-dim sm:px-7 sm:pt-7 sm:pb-[26px]">
        <span class="flex flex-wrap items-center gap-x-[18px] gap-y-1.5 ${META}">
          <span class="font-semibold text-signal">Latest</span>
          <time datetime="${latest.date}">${longDate(latest.date)}</time>
          <span class="normal-case tracking-[0.02em]">#${esc(latest.topic)}</span>
          <span>${latest.readingMinutes} min read</span>
        </span>
        <span class="mt-4 block font-display text-[clamp(26px,3.6vw,34px)] font-bold leading-[1.12] tracking-[-0.02em] text-paper">${esc(latest.title)}</span>
        <span class="mt-3 block max-w-[60ch] text-[16px] leading-[1.6] text-[#a9ab95]">${esc(latest.description)}</span>
        <span class="mt-5 inline-flex items-center gap-2 font-wire text-[12px] tracking-[0.04em] text-signal">Read the issue ${ARROW_RIGHT}</span>
      </a>`
    : `
      <p class="mt-14 text-[#a9ab95]">No issues yet.</p>`

  const months: { label: string; posts: PostMeta[] }[] = []
  for (const p of rest) {
    const label = monthLabel(p.date)
    if (months.at(-1)?.label !== label) months.push({ label, posts: [] })
    months.at(-1)!.posts.push(p)
  }
  const groups = months
    .map(
      (g) => `        <p class="mt-7 ${META} tracking-[0.12em]">${g.label}</p>
        <ol class="mt-2 list-none p-0">
${g.posts
  .map(
    (
      p,
    ) => `          <li class="grid grid-cols-[64px_minmax(0,1fr)] gap-x-4 border-b border-wire py-6 sm:gap-x-6">
            <time datetime="${p.date}" class="pt-[5px] font-wire text-[12px] uppercase tracking-[0.04em] tabular-nums text-dim">${shortDate(p.date)}</time>
            <div class="flex min-w-0 flex-col gap-2">
              <h3 class="font-display text-[21px] font-semibold leading-[1.25] tracking-[-0.01em]"><a href="${postHref(p)}" class="text-paper hover:text-signal">${esc(p.title)}</a></h3>
              <p class="max-w-[62ch] text-[15px] leading-[1.55] text-[#a9ab95]">${esc(p.description)}</p>
              <p class="mt-0.5 flex flex-wrap gap-x-4 gap-y-1 font-wire text-[11px] text-dim"><span>#${esc(p.topic)}</span><span>${p.readingMinutes} min read</span></p>
            </div>
          </li>`,
  )
  .join("\n")}
        </ol>`,
    )
    .join("\n")
  const archive = rest.length
    ? `
      <section aria-labelledby="archive" class="mt-[72px]">
        <div class="${SECTION_HEAD}">
          <h2 id="archive" class="text-paper">Archive</h2>
          <span>${posts.length} issues</span>
        </div>
${groups}
      </section>`
    : ""

  const main = `    <main class="mx-auto box-border w-full max-w-[768px] flex-1 px-4 pt-16 pb-[88px]">
      <p class="flex items-center gap-2.5 ${META} tracking-[0.12em]"><span aria-hidden="true" class="inline-block h-2 w-2 bg-signal"></span>The weekly issue</p>
      <h1 class="mt-[18px] max-w-[15ch] font-display text-[clamp(38px,6vw,60px)] font-extrabold leading-[1.02] tracking-[-0.03em] text-paper">One AI topic a week, explained plainly.</h1>
      <p class="mt-[22px] max-w-[54ch] text-[17px] leading-[1.6] text-[#a9ab95]">Each issue takes the most talked-about topic in the ${SITE_NAME} feed and explains what it is, how it works, and what the people who tried it found.</p>${latestBlock}${archive}
    </main>`

  return shell({
    title: "Blog",
    description: `One AI topic a week, explained plainly, from the ${SITE_NAME} feed.`,
    canonicalPath: "/blog/",
    cssHrefs,
    ogType: "website",
    current: "index",
    main,
  })
}

// Real, indexable SPA routes. Everything else (/developers, /newsletter,
// login, settings, admin, profile) sits behind the login guard and bounces
// anonymous visitors (and crawlers) to "/", so there's nothing there for
// Google to rank.
const STATIC_ROUTES = ["/"]

function renderSitemap(posts: PostMeta[]): string {
  const today = new Date().toISOString().slice(0, 10)
  const urls = [
    ...STATIC_ROUTES.map((route) => ({ loc: route, lastmod: today })),
    { loc: "/blog/", lastmod: posts[0]?.date ?? today },
    ...posts.map((p) => ({ loc: postHref(p), lastmod: p.date })),
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

// ─── Main ────────────────────────────────────────────────────────────────────

function cssHrefs(): string[] {
  const assetsDir = path.join(DIST_DIR, "assets")
  if (!fs.existsSync(assetsDir)) {
    console.error(
      "prerender-blog: dist/assets not found, run `vite build` first",
    )
    process.exit(1)
  }
  return fs
    .readdirSync(assetsDir)
    .filter((f) => f.endsWith(".css"))
    .map((f) => `/assets/${f}`)
}

/** Render everything. Returns false, having printed why, if a post is broken. */
async function render(): Promise<boolean> {
  const { posts, errors } = loadPosts()
  if (errors.length > 0) {
    console.error("prerender-blog: posts that can't be rendered:")
    for (const e of errors) console.error(`  - ${e}`)
    return false
  }

  const css = cssHrefs()
  const md = markdown(await loadHighlighter(posts))
  const blogDir = path.join(DIST_DIR, "blog")
  fs.rmSync(blogDir, { recursive: true, force: true })
  for (const p of posts) {
    const dir = path.join(blogDir, p.slug)
    fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(
      path.join(dir, "index.html"),
      renderPost(p, posts, md, css),
    )
  }
  fs.mkdirSync(blogDir, { recursive: true })
  fs.writeFileSync(path.join(blogDir, "index.html"), renderIndex(posts, css))
  fs.writeFileSync(path.join(DIST_DIR, "sitemap.xml"), renderSitemap(posts))

  console.log(`prerender-blog: rendered ${posts.length} post(s) + index`)
  return true
}

const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".xml": "application/xml",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
}

function serve(port: number) {
  http
    .createServer((req, res) => {
      const url = new URL(req.url ?? "/", "http://localhost")
      let file = path.join(DIST_DIR, decodeURIComponent(url.pathname))
      if (!file.startsWith(DIST_DIR)) file = DIST_DIR
      if (fs.existsSync(file) && fs.statSync(file).isDirectory())
        file = path.join(file, "index.html")
      if (!fs.existsSync(file)) {
        res.writeHead(404, { "Content-Type": "text/plain" }).end("Not found")
        return
      }
      res.writeHead(200, {
        "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream",
        "Cache-Control": "no-store",
      })
      fs.createReadStream(file).pipe(res)
    })
    .listen(port, () =>
      console.log(
        `prerender-blog: serving dist/ on http://localhost:${port}/blog/`,
      ),
    )
}

async function watch() {
  await render()
  serve(Number(process.env.PORT ?? 4174))
  let timer: ReturnType<typeof setTimeout> | undefined
  fs.watch(CONTENT_DIR, () => {
    clearTimeout(timer)
    timer = setTimeout(() => void render(), 100)
  })
  console.log("prerender-blog: watching content/blog/")
}

if (process.argv.includes("--watch")) await watch()
else if (!(await render())) process.exit(1)

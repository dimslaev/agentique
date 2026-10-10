/**
 * Blog posts as data: reads content/blog/*.md and returns each post's
 * metadata and body markdown. No HTML, no styling. prerender-blog.ts renders
 * from it, and a Vite plugin can import it to feed the app a list of posts.
 *
 * Only structural checks live here: what a page needs to render. The content
 * rules for an issue (lengths, word count, sources) live in
 * backend/app/newsletter/broadcast.py, which refuses a post before it is ever
 * drafted.
 */

import fs from "node:fs"
import path from "node:path"
import { marked, type Token } from "marked"
import YAML from "yaml"

export const CONTENT_DIR = path.resolve(
  import.meta.dirname,
  "..",
  "content",
  "blog",
)

const FILE_RE = /^(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$/
const WORDS_PER_MINUTE = 230

export type PostLink = {
  url: string
  // The link's text, markup stripped.
  text: string
  // The host without "www.", for showing beside the link.
  domain: string
}

export type PostMeta = {
  file: string
  slug: string
  // YYYY-MM-DD, from the filename.
  date: string
  title: string
  description: string
  topic: string
  readingMinutes: number
  // The body's distinct http(s) links, in the order they first appear.
  links: PostLink[]
  bodyMd: string
}

export type LoadResult = { posts: PostMeta[]; errors: string[] }

function scalar(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "object") return ""
  return String(value).trim()
}

function plainText(tokens: Token[]): string {
  return tokens
    .map((t) => {
      if ("tokens" in t && t.tokens) return plainText(t.tokens)
      return "text" in t ? t.text : ""
    })
    .join("")
}

export function bodyLinks(bodyMd: string): PostLink[] {
  const out: PostLink[] = []
  const seen = new Set<string>()
  marked.walkTokens(marked.lexer(bodyMd), (t) => {
    if (t.type !== "link" || !/^https?:\/\//.test(t.href)) return
    if (seen.has(t.href)) return
    seen.add(t.href)
    out.push({
      url: t.href,
      text: plainText(t.tokens ?? []) || t.href,
      domain: new URL(t.href).hostname.replace(/^www\./, ""),
    })
  })
  return out
}

export function readingMinutes(bodyMd: string): number {
  const words = bodyMd.split(/\s+/).filter(Boolean).length
  return Math.max(1, Math.ceil(words / WORDS_PER_MINUTE))
}

/** Parse one post file. Returns the post, or the reasons it can't be one. */
export function parsePost(
  file: string,
  raw: string,
  today: string,
): PostMeta | string[] {
  const errors: string[] = []
  const name = FILE_RE.exec(file)
  if (!name) errors.push("filename must be YYYY-MM-DD-slug.md")

  const text = raw.replaceAll("\r\n", "\n")
  if (!text.startsWith("---\n"))
    return [...errors, "missing frontmatter (file must start with ---)"]
  const end = text.indexOf("\n---\n", 3)
  if (end === -1) return [...errors, "unterminated frontmatter"]

  let fm: unknown
  try {
    fm = YAML.parse(text.slice(4, end))
  } catch (e) {
    return [...errors, `frontmatter is not valid YAML: ${e}`]
  }
  if (typeof fm !== "object" || fm === null || Array.isArray(fm))
    return [...errors, "frontmatter is not a key: value map"]
  const fields = fm as Record<string, unknown>

  const title = scalar(fields.title)
  const description = scalar(fields.description)
  const topic = scalar(fields.topic)
  if (!title) errors.push("missing title")
  if (!description) errors.push("missing description")
  if (!topic) errors.push("missing topic")

  const date = name?.[1] ?? ""
  if (name) {
    if (Number.isNaN(Date.parse(date))) errors.push(`invalid date ${date}`)
    else if (date > today) errors.push(`date ${date} is in the future`)
  }

  if (errors.length > 0) return errors
  const bodyMd = text.slice(end + 5).trim()
  return {
    file,
    slug: name![2],
    date,
    title,
    description,
    topic,
    readingMinutes: readingMinutes(bodyMd),
    links: bodyLinks(bodyMd),
    bodyMd,
  }
}

/** Every post in `dir`, newest first, and every structural problem found. */
export function loadPosts(dir: string = CONTENT_DIR): LoadResult {
  const today = new Date().toISOString().slice(0, 10)
  const files = fs.existsSync(dir)
    ? fs
        .readdirSync(dir)
        .filter((f) => f.endsWith(".md"))
        .sort()
    : []

  const posts: PostMeta[] = []
  const errors: string[] = []
  const seen = new Set<string>()
  for (const file of files) {
    const result = parsePost(
      file,
      fs.readFileSync(path.join(dir, file), "utf-8"),
      today,
    )
    if (Array.isArray(result)) {
      errors.push(...result.map((e) => `${file}: ${e}`))
      continue
    }
    if (seen.has(result.slug))
      errors.push(`${file}: duplicate slug "${result.slug}"`)
    seen.add(result.slug)
    posts.push(result)
  }

  posts.sort(
    (a, b) => b.date.localeCompare(a.date) || b.file.localeCompare(a.file),
  )
  return { posts, errors }
}

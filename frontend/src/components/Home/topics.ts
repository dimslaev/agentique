// Landing-page lanes.
//
// One lane per category, and that is the whole definition. There is nothing to
// choose here any more: the pipeline stores an article only if it matches a
// category, so the lane list *is* the category list, and the site has no
// articles outside it.
//
// This file used to hold hand-tuned unions of tags crossed with kinds, because
// no single filter expressed a lane and /feed is single-select. Each box
// expanded into up to six requests merged client-side, and tag∩tag lanes could
// not be expressed correctly at all (see plans/topic-boxes-homepage.md).
// Deciding membership at ingest deleted that problem rather than solving it:
// every lane is now one indexed request.
//
// The lanes themselves come from the server (`GET /articles/categories`, in
// `Category.position` order), so re-ordering the homepage or rewording a lane
// is a DB update, not a deploy.

export type TopicDef = {
  /** Category slug — the only filter a lane needs. */
  slug: string
  label: string
}

/** Rows shown per lane, and the page size of its single request. */
export const BOX_LIMIT = 10

/** Newest first, matching /feed's own default. */
export const BOX_SORT = "published_at-desc"

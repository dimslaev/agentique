import { CodeBlock } from "./code-block"
import { EndpointCard } from "./endpoint-card"

const RESPONSE_SHAPE = `{
  "data": [
    {
      "id": 1,
      "title": "string",
      "url": "string",
      "published_at": "ISO datetime | null",
      "score": "integer",
      "summary": "string | null",
      "kind": "post | repo | paper | model",
      "found_via": "string | null",
      "created_at": "ISO datetime | null",
      "publisher": {
        "id": 1,
        "slug": "string",
        "name": "string",
        "kind": "lab | company | individual | media | community | unknown",
        "image": "string | null"
      },
      "tags": [{ "slug": "string", "name": "string" }],
      "like_count": "integer",
      "liked_by_me": "boolean"
    }
  ],
  "count": "integer"
}`

/** The public API's endpoints and the shape they answer with. */
export function ApiReference() {
  return (
    <>
      <div className="space-y-6">
        <EndpointCard
          method="GET"
          path="/api/v1/articles"
          description="List recent articles with optional filters."
          params={[
            {
              name: "since",
              description: "ISO date · optional · omit for all-time",
            },
            { name: "limit", description: "integer · 1-50 · default 20" },
            {
              name: "q",
              description: "string · optional · title/content match",
            },
            { name: "min_score", description: "integer · 1-10 · optional" },
            {
              name: "origin",
              description:
                "lab | company | individual | media | repo | paper | model · optional · a repo, paper or model by kind, anything else by its publisher's kind",
            },
            {
              name: "kind",
              description: "post | repo | paper | model · optional",
            },
            { name: "tag", description: "tag slug · optional" },
            {
              name: "sort",
              description:
                "score-desc (default) | published_at-desc | likes-desc",
            },
          ]}
        />

        <EndpointCard
          method="GET"
          path="/api/v1/articles/search"
          description="Semantic search over articles using natural language."
          params={[
            {
              name: "q",
              description: "string · required · natural language query",
            },
            { name: "limit", description: "integer · 1-50 · default 20" },
          ]}
        />
      </div>

      <div className="space-y-3">
        <h2 className="font-wire text-xs uppercase tracking-[0.1em] text-muted-foreground">
          Response
        </h2>
        <CodeBlock code={RESPONSE_SHAPE} />
      </div>
    </>
  )
}

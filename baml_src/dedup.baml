class DedupMatch {
  url string @description("URL of the new article")
  existingUrl string @description("URL of the existing article it duplicates")
}

function SemanticDedup(
  newArticles: ArticleInput[],
  existingArticles: ExistingArticle[]
) -> DedupMatch[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a semantic similarity engine. You compare article pairs and determine whether they cover the same underlying story. You focus on substance, not surface-level keyword overlap.

    {{ _.role("user") }}
    You are given two lists:
    1. NEW articles that were just fetched
    2. EXISTING articles already in our database from the last 14 days

    Your job: identify which NEW articles are about the same story as an EXISTING article. Two articles are "the same story" if they cover the same announcement, release, event, or topic - even if from different sources or with different angles.

    NEW articles:
    {% for a in newArticles %}
    {{ loop.index }}. [{{ a.source }}] "{{ a.title }}" - {{ a.url }}{% if a.trust %} [trust: {{ a.trust }}]{% endif %}
    {% if a.snippet %}   {{ a.snippet }}{% endif %}
    {% endfor %}

    EXISTING articles:
    {% for a in existingArticles %}
    {{ loop.index }}. [{{ a.source }}] "{{ a.title }}" - {{ a.url }}
    {% endfor %}

    For each match, return the new article's URL and the existing article's URL.
    If there are no duplicates, return an empty list.

    {{ ctx.output_format }}
  "#
}

test dedup_no_matches {
  functions [SemanticDedup]
  args {
    newArticles [
      {
        url "https://a.com/1"
        title "Claude 4 released"
        source "HN"
      }
    ]
    existingArticles [
      {
        url "https://b.com/1"
        title "The state of Rust in 2026"
        source "RSS"
      }
    ]
  }
}

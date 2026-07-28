// Shared types used by multiple BAML functions.

enum ArticleKind {
  Repo         // GitHub/GitLab repository
  Paper        // Academic paper, preprint, technical report
  Model        // Model card or model release page
  Blog         // Developer blog post, tutorial, how-to, opinion piece
  Product      // Product launch page or product website
  Announcement // Official release post from a major AI lab
}

// Used as input to MatchCategories, ImproveTitles, SemanticDedup.
// Mirrors the fields the existing formatArticles() helper emits.
class ArticleInput {
  url string
  title string
  source string
  snippet string? @description("First ~200 chars of the article content, if any")
  trust string? @description("\"high\" | \"medium\" | \"low\" - source trust tag")
}

// Used as input to SemanticDedup for rows already in the DB.
class ExistingArticle {
  url string
  title string
  source string
}

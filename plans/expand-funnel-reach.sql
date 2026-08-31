-- Cloud, chips, dev tools, AI infra — plain RSS, ungated (43)
insert into publisher
  (slug, name, kind, type, trust, is_active, topic_gated, links, created_at)
select v.slug, v.name, 'company'::publisherkind, v.type::publishertype,
       'medium'::trustlevel, true, v.topic_gated, v.links::json, now()
from (values
  ('cloudflare', 'Cloudflare', 'rss', false,
   '{"rss":"https://blog.cloudflare.com/rss/","website":"https://blog.cloudflare.com"}'),
  ('aws-machine-learning', 'AWS Machine Learning', 'rss', false,
   '{"rss":"https://aws.amazon.com/blogs/machine-learning/feed/","website":"https://aws.amazon.com"}'),
  ('aws-news-ai', 'AWS News AI', 'rss', false,
   '{"rss":"https://aws.amazon.com/blogs/aws/category/artificial-intelligence/feed/","website":"https://aws.amazon.com"}'),
  ('nvidia-developer', 'NVIDIA Developer', 'rss', false,
   '{"rss":"https://developer.nvidia.com/blog/feed/","website":"https://developer.nvidia.com"}'),
  ('nvidia-blog', 'NVIDIA Blog', 'rss', false,
   '{"rss":"https://blogs.nvidia.com/feed/","website":"https://blogs.nvidia.com"}'),
  ('google-cloud-ai', 'Google Cloud AI', 'rss', false,
   '{"rss":"https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/","website":"https://cloudblog.withgoogle.com"}'),
  ('google-research', 'Google Research', 'rss', false,
   '{"rss":"https://research.google/blog/rss/","website":"https://research.google"}'),
  ('microsoft-azure', 'Microsoft Azure', 'rss', false,
   '{"rss":"https://azure.microsoft.com/en-us/blog/feed/","website":"https://azure.microsoft.com"}'),
  ('meta-engineering', 'Meta Engineering', 'rss', false,
   '{"rss":"https://engineering.fb.com/feed/","website":"https://engineering.fb.com"}'),
  ('amazon-science', 'Amazon Science', 'rss', false,
   '{"rss":"https://www.amazon.science/index.rss","website":"https://www.amazon.science"}'),
  ('apple-ml-research', 'Apple ML Research', 'rss', false,
   '{"rss":"https://machinelearning.apple.com/rss.xml","website":"https://machinelearning.apple.com"}'),
  ('intel-ai', 'Intel AI', 'rss', false,
   '{"rss":"https://community.intel.com/rss/board?board.id=blog-ai","website":"https://community.intel.com"}'),
  ('arm-newsroom', 'Arm Newsroom', 'rss', false,
   '{"rss":"https://newsroom.arm.com/rss","website":"https://newsroom.arm.com"}'),
  ('sonar', 'Sonar', 'rss', false,
   '{"rss":"https://www.sonarsource.com/blog/rss.xml","website":"https://www.sonarsource.com"}'),
  ('github-ai-ml', 'GitHub AI & ML', 'rss', false,
   '{"rss":"https://github.blog/ai-and-ml/feed/","website":"https://github.blog"}'),
  ('jetbrains', 'JetBrains', 'rss', false,
   '{"rss":"https://blog.jetbrains.com/feed/","website":"https://blog.jetbrains.com"}'),
  ('gitlab', 'GitLab', 'rss', false,
   '{"rss":"https://about.gitlab.com/atom.xml","website":"https://about.gitlab.com"}'),
  ('sourcegraph', 'Sourcegraph', 'rss', false,
   '{"rss":"https://sourcegraph.com/blog/rss.xml","website":"https://sourcegraph.com"}'),
  ('docker', 'Docker', 'rss', false,
   '{"rss":"https://www.docker.com/feed/","website":"https://www.docker.com"}'),
  ('vercel', 'Vercel', 'rss', false,
   '{"rss":"https://vercel.com/atom","website":"https://vercel.com"}'),
  ('supabase', 'Supabase', 'rss', false,
   '{"rss":"https://supabase.com/rss.xml","website":"https://supabase.com"}'),
  ('sentry', 'Sentry', 'rss', false,
   '{"rss":"https://blog.sentry.io/feed.xml","website":"https://blog.sentry.io"}'),
  ('datadog', 'Datadog', 'rss', false,
   '{"rss":"https://www.datadoghq.com/blog/index.xml","website":"https://www.datadoghq.com"}'),
  ('hashicorp', 'HashiCorp', 'rss', false,
   '{"rss":"https://www.hashicorp.com/blog/feed.xml","website":"https://www.hashicorp.com"}'),
  ('grafana', 'Grafana', 'rss', false,
   '{"rss":"https://grafana.com/blog/index.xml","website":"https://grafana.com"}'),
  ('elastic', 'Elastic', 'rss', false,
   '{"rss":"https://www.elastic.co/blog/feed","website":"https://www.elastic.co"}'),
  ('redis', 'Redis', 'rss', false,
   '{"rss":"https://redis.io/blog/feed/","website":"https://redis.io"}'),
  ('stack-overflow', 'Stack Overflow', 'rss', false,
   '{"rss":"https://stackoverflow.blog/feed/","website":"https://stackoverflow.blog"}'),
  ('zed', 'Zed', 'rss', false,
   '{"rss":"https://zed.dev/blog.rss","website":"https://zed.dev"}'),
  ('deno', 'Deno', 'rss', false,
   '{"rss":"https://deno.com/feed","website":"https://deno.com"}'),
  ('bun', 'Bun', 'rss', false,
   '{"rss":"https://bun.com/rss.xml","website":"https://bun.com"}'),
  ('fly-io', 'Fly.io', 'rss', false,
   '{"rss":"https://fly.io/blog/feed.xml","website":"https://fly.io"}'),
  ('tailscale', 'Tailscale', 'rss', false,
   '{"rss":"https://tailscale.com/blog/index.xml","website":"https://tailscale.com"}'),
  ('snyk', 'Snyk', 'rss', false,
   '{"rss":"https://snyk.io/blog/feed/","website":"https://snyk.io"}'),
  ('wiz', 'Wiz', 'rss', false,
   '{"rss":"https://www.wiz.io/blog/rss.xml","website":"https://www.wiz.io"}'),
  ('jfrog', 'JFrog', 'rss', false,
   '{"rss":"https://jfrog.com/blog/feed/","website":"https://jfrog.com"}'),
  ('pytorch', 'PyTorch', 'rss', false,
   '{"rss":"https://pytorch.org/blog/feed.xml","website":"https://pytorch.org"}'),
  ('ollama', 'Ollama', 'rss', false,
   '{"rss":"https://ollama.com/blog/rss.xml","website":"https://ollama.com"}'),
  ('replicate', 'Replicate', 'rss', false,
   '{"rss":"https://replicate.com/blog/rss","website":"https://replicate.com"}'),
  ('together-ai', 'Together AI', 'rss', false,
   '{"rss":"https://www.together.ai/blog/rss.xml","website":"https://www.together.ai"}'),
  ('weaviate', 'Weaviate', 'rss', false,
   '{"rss":"https://weaviate.io/blog/rss.xml","website":"https://weaviate.io"}'),
  ('netflix-tech-ml', 'Netflix Tech ML', 'rss', false,
   '{"rss":"https://netflixtechblog.com/feed/tagged/machine-learning","website":"https://netflixtechblog.com"}'),
  ('databricks', 'Databricks', 'rss', false,
   '{"rss":"https://www.databricks.com/feed","website":"https://www.databricks.com"}')
) as v(slug, name, type, topic_gated, links)
where not exists (select 1 from publisher p where p.slug = v.slug);

-- Broad engineering blogs — RSS, title-gated on AI keywords (11)
insert into publisher
  (slug, name, kind, type, trust, is_active, topic_gated, links, created_at)
select v.slug, v.name, 'company'::publisherkind, v.type::publishertype,
       'medium'::trustlevel, true, v.topic_gated, v.links::json, now()
from (values
  ('stripe', 'Stripe', 'rss', true,
   '{"rss":"https://stripe.com/blog/feed.rss","website":"https://stripe.com"}'),
  ('salesforce-engineering', 'Salesforce Engineering', 'rss', true,
   '{"rss":"https://engineering.salesforce.com/feed/","website":"https://engineering.salesforce.com"}'),
  ('spotify-engineering', 'Spotify Engineering', 'rss', true,
   '{"rss":"https://engineering.atspotify.com/feed","website":"https://engineering.atspotify.com"}'),
  ('airbnb-engineering', 'Airbnb Engineering', 'rss', true,
   '{"rss":"https://medium.com/feed/airbnb-engineering","website":"https://medium.com"}'),
  ('pinterest-engineering', 'Pinterest Engineering', 'rss', true,
   '{"rss":"https://medium.com/feed/pinterest-engineering","website":"https://medium.com"}'),
  ('palantir', 'Palantir', 'rss', true,
   '{"rss":"https://blog.palantir.com/feed","website":"https://blog.palantir.com"}'),
  ('sap-news', 'SAP News', 'rss', true,
   '{"rss":"https://news.sap.com/feed/","website":"https://news.sap.com"}'),
  ('postman', 'Postman', 'rss', true,
   '{"rss":"https://blog.postman.com/feed/","website":"https://blog.postman.com"}'),
  ('auth0', 'Auth0', 'rss', true,
   '{"rss":"https://auth0.com/blog/rss.xml","website":"https://auth0.com"}'),
  ('okta-developer', 'Okta Developer', 'rss', true,
   '{"rss":"https://developer.okta.com/feed.xml","website":"https://developer.okta.com"}'),
  ('figma', 'Figma', 'rss', true,
   '{"rss":"https://www.figma.com/blog/feed/atom.xml","website":"https://www.figma.com"}')
) as v(slug, name, type, topic_gated, links)
where not exists (select 1 from publisher p where p.slug = v.slug);

-- Lab Watch targets — no working RSS, discovered first-party via search (14)
insert into publisher
  (slug, name, kind, type, trust, is_active, topic_gated, links, created_at)
select v.slug, v.name, 'company'::publisherkind, v.type::publishertype,
       'medium'::trustlevel, true, v.topic_gated, v.links::json, now()
from (values
  ('cursor', 'Cursor', 'search', false,
   '{"search":"cursor.com","website":"https://cursor.com"}'),
  ('perplexity', 'Perplexity', 'search', false,
   '{"search":"perplexity.ai","website":"https://perplexity.ai"}'),
  ('groq', 'Groq', 'search', false,
   '{"search":"groq.com","website":"https://groq.com"}'),
  ('cohere', 'Cohere', 'search', false,
   '{"search":"cohere.com","website":"https://cohere.com"}'),
  ('elevenlabs', 'ElevenLabs', 'search', false,
   '{"search":"elevenlabs.io","website":"https://elevenlabs.io"}'),
  ('modal', 'Modal', 'search', false,
   '{"search":"modal.com","website":"https://modal.com"}'),
  ('pinecone', 'Pinecone', 'search', false,
   '{"search":"pinecone.io","website":"https://pinecone.io"}'),
  ('llamaindex', 'LlamaIndex', 'search', false,
   '{"search":"llamaindex.ai","website":"https://llamaindex.ai"}'),
  ('cerebras', 'Cerebras', 'search', false,
   '{"search":"cerebras.ai","website":"https://cerebras.ai"}'),
  ('snowflake', 'Snowflake', 'search', false,
   '{"search":"snowflake.com","website":"https://snowflake.com"}'),
  ('runway', 'Runway', 'search', false,
   '{"search":"runwayml.com","website":"https://runwayml.com"}'),
  ('stability-ai', 'Stability AI', 'search', false,
   '{"search":"stability.ai","website":"https://stability.ai"}'),
  ('meta-ai', 'Meta AI', 'search', false,
   '{"search":"ai.meta.com","website":"https://ai.meta.com"}'),
  ('replit', 'Replit', 'search', false,
   '{"search":"replit.com","website":"https://replit.com"}')
) as v(slug, name, type, topic_gated, links)
where not exists (select 1 from publisher p where p.slug = v.slug);

-- Reddit — the source module polls r/LocalLLaMA and r/MachineLearning (1)
insert into publisher
  (slug, name, kind, type, trust, is_active, topic_gated, links, created_at)
select v.slug, v.name, 'community'::publisherkind, v.type::publishertype,
       'medium'::trustlevel, true, v.topic_gated, v.links::json, now()
from (values
  ('reddit', 'Reddit', 'reddit', false,
   '{"website":"https://www.reddit.com"}')
) as v(slug, name, type, topic_gated, links)
where not exists (select 1 from publisher p where p.slug = v.slug);


CREATE TABLE IF NOT EXISTS rss_articles (
  id BIGSERIAL PRIMARY KEY,
  article_id TEXT NOT NULL UNIQUE,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rss_articles_id ON rss_articles (article_id);
CREATE INDEX IF NOT EXISTS idx_rss_articles_fetched ON rss_articles (fetched_at DESC);

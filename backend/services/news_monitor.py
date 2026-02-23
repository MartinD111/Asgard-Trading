"""
News Monitor — background service that scrapes RSS feeds every 60s,
stores summaries in ChromaDB for RAG retrieval by GeminiPredictor.
"""
import os
import sys
import time
import asyncio
import hashlib
import logging
from datetime import datetime

import feedparser
import chromadb
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

NEWS_SOURCES = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters Markets", "https://feeds.reuters.com/reuters/marketsNews"),
    ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
    ("FT Markets", "https://www.ft.com/markets?format=rss"),
    ("Investing.com Forex", "https://www.investing.com/rss/news_25.rss"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
]


def _article_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}:{title}".encode()).hexdigest()[:16]


class NewsMonitor:
    def __init__(self, chroma_path: str = "/app/chroma_db"):
        api_key = os.getenv("GEMINI_API_KEY", "")
        self.has_embeddings = bool(api_key)

        self.chroma = chromadb.PersistentClient(path=chroma_path)

        embed_fn = None
        if self.has_embeddings:
            embed_fn = GoogleGenerativeAiEmbeddingFunction(
                api_key=api_key,
                model_name="models/embedding-001",
            )

        self.collection = self.chroma.get_or_create_collection(
            name="market_news",
            embedding_function=embed_fn,
        )

        self._seen: set[str] = set()

    def fetch_news(self) -> list[dict]:
        articles = []
        for source_name, url in NEWS_SOURCES:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:
                    article_id = _article_id(entry.get("link", ""), entry.get("title", ""))
                    if article_id in self._seen:
                        continue
                    self._seen.add(article_id)
                    articles.append({
                        "id": article_id,
                        "source": source_name,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", ""))[:500],
                        "published": entry.get("published", datetime.utcnow().isoformat()),
                        "url": entry.get("link", ""),
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch {source_name}: {e}")
        return articles

    def store_articles(self, articles: list[dict]):
        if not articles:
            return
        self.collection.add(
            ids=[a["id"] for a in articles],
            documents=[f"{a['title']}. {a['summary']}" for a in articles],
            metadatas=[{
                "source": a["source"],
                "published": a["published"],
                "url": a["url"],
            } for a in articles],
        )
        logger.info(f"Stored {len(articles)} new articles in ChromaDB.")

    def query_relevant(self, query: str, n_results: int = 10) -> list[str]:
        """RAG retrieval — returns top-N relevant headlines for a given query."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, self.collection.count()),
            )
            headlines = []
            for doc, meta in zip(
                results.get("documents", [[]])[0],
                results.get("metadatas", [[]])[0],
            ):
                headlines.append(f"[{meta.get('source','')}] {doc[:200]}")
            return headlines
        except Exception as e:
            logger.warning(f"RAG query error: {e}")
            return []

    async def run_loop(self, interval: int = 60):
        """Async loop — fetches every `interval` seconds."""
        while True:
            try:
                articles = self.fetch_news()
                self.store_articles(articles)
            except Exception as e:
                logger.error(f"NewsMonitor loop error: {e}")
            await asyncio.sleep(interval)


# ─── Standalone entrypoint (docker news-monitor service) ──────
if __name__ == "__main__" or (len(sys.argv) > 1 and "--standalone" in sys.argv):
    monitor = NewsMonitor()
    asyncio.run(monitor.run_loop())

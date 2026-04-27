#!/bin/bash
DB="/Users/unclejoe/Media_Workspace/ai-daily-news/db/news.db"
SOURCES="/Users/unclejoe/Media_Workspace/ai-daily-news/db/sources.json"
cd /Users/unclejoe/Media_Workspace/ai-daily-news/db
python3 news_db.py "$DB" --init
python3 news_db.py "$DB" --import-sources "$SOURCES"
python3 news_db.py "$DB" --backfill /Users/unclejoe/Media_Workspace/ai-daily-news/daily
python3 news_db.py "$DB" --stats

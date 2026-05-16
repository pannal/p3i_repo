#!/usr/bin/env python3
# coding=utf-8
"""
Enrich PM4K's seamless_branching.json with TMDB IDs.

Reads TMDB credentials from environment:
    TMDB_BEARER     -- v4 read-access token (preferred)
    TMDB_API_KEY    -- v3 api key (fallback)

Usage:
    TMDB_BEARER=... python3 tools/enrich_tmdb.py \
        --source /mnt/d/data/___small/script.plexmod/resources/seamless_branching.json \
        --out resources/seamless_branching.json

If --out exists, it is read first; entries with a tmdb_id already present are
left untouched (so re-running is cheap).
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

TMDB_FIND_URL = "https://api.themoviedb.org/3/find/{imdb_id}?external_source=imdb_id"


def get_credentials():
    bearer = os.environ.get("TMDB_BEARER", "").strip()
    api_key = os.environ.get("TMDB_API_KEY", "").strip()
    if not bearer and not api_key:
        sys.stderr.write("error: set TMDB_BEARER or TMDB_API_KEY in the environment\n")
        sys.exit(2)
    return bearer, api_key


def lookup_tmdb_id(imdb_id, bearer, api_key, timeout=10):
    url = TMDB_FIND_URL.format(imdb_id=urllib.parse.quote(imdb_id))
    headers = {"Accept": "application/json"}
    if bearer:
        headers["Authorization"] = "Bearer {}".format(bearer)
    elif api_key:
        url = url + "&api_key={}".format(urllib.parse.quote(api_key))
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        sys.stderr.write("  ! lookup failed for {}: {}\n".format(imdb_id, exc))
        return None
    movies = data.get("movie_results") or []
    if not movies:
        return None
    return movies[0].get("id")


def load_existing(out_path):
    if not os.path.exists(out_path):
        return {}
    try:
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        sys.stderr.write("warn: could not read existing {}: {}\n".format(out_path, exc))
        return {}
    return {m["imdb_id"]: m for m in data.get("movies", []) if m.get("imdb_id")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True,
                   help="Path to PM4K's seamless_branching.json")
    p.add_argument("--out", required=True,
                   help="Output path for enriched JSON (addon's resources/seamless_branching.json)")
    p.add_argument("--sleep", type=float, default=0.1,
                   help="Seconds between TMDB requests (rate-limit politeness; default 0.1)")
    p.add_argument("--force", action="store_true",
                   help="Re-fetch TMDB IDs even if already present in --out")
    args = p.parse_args()

    bearer, api_key = get_credentials()

    with open(args.source, "r", encoding="utf-8") as f:
        source = json.load(f)

    existing = load_existing(args.out)

    out_movies = []
    fetched = 0
    skipped = 0
    misses = 0
    for entry in source.get("movies", []):
        imdb_id = entry.get("imdb_id")
        if not imdb_id:
            out_movies.append(dict(entry))
            continue
        prev = existing.get(imdb_id, {})
        new = dict(entry)
        if prev.get("tmdb_id") and not args.force:
            new["tmdb_id"] = prev["tmdb_id"]
            skipped += 1
            out_movies.append(new)
            continue
        tmdb_id = lookup_tmdb_id(imdb_id, bearer, api_key)
        if tmdb_id:
            new["tmdb_id"] = tmdb_id
            fetched += 1
            print("  {} -> tmdb {}  ({})".format(imdb_id, tmdb_id, entry.get("title", "?")))
        else:
            misses += 1
            print("  {} -> NO MATCH  ({})".format(imdb_id, entry.get("title", "?")))
        out_movies.append(new)
        time.sleep(args.sleep)

    enriched = {
        "version": source.get("version", 1),
        "last_updated": source.get("last_updated"),
        "source": source.get("source"),
        "description": source.get("description"),
        "movies": out_movies,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("\nfetched={} skipped(cached)={} misses={} total={}".format(
        fetched, skipped, misses, len(out_movies)))


if __name__ == "__main__":
    main()

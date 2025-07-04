#!/usr/bin/env python3
import os
import requests

def get_tmdb_api_key():
    return os.getenv("TMDB_API_KEY")

def search_tmdb_movie(title, year=None):
    api_key = get_tmdb_api_key()
    if not api_key:
        print("TMDB_API_KEY not set in environment.")
        return None
    params = {
        "api_key": api_key,
        "query": title,
        "language": "en-US",
    }
    if year:
        params["year"] = year
    resp = requests.get("https://api.themoviedb.org/3/search/movie", params=params)
    if resp.status_code == 200:
        return resp.json().get("results", [])
    else:
        print(f"TMDB API error: {resp.status_code} {resp.text}")
        return None

def main():
    print("TMDB Integration Test Tool")
    title = input("Enter movie title: ").strip()
    year = input("Enter year (optional): ").strip()
    year = year if year else None
    results = search_tmdb_movie(title, year)
    if results is None:
        print("No results or error.")
        return
    if not results:
        print("No matches found.")
        return
    print(f"\nResults for '{title}' ({year}):")
    for movie in results:
        print(f"- {movie['title']} ({movie.get('release_date', 'N/A')[:4]}) [tmdb-{movie['id']}]")

if __name__ == "__main__":
    main()
# filepath: /home/adam/Desktop/Scanly/tools/tmdb_test.py
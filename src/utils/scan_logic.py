import re
import datetime
import unicodedata
import os
import difflib
from .cleaning_patterns import patterns_to_remove

def extract_folder_metadata(folder_name):
    clean_title = folder_name
    year = None
    parentheses_year = re.search(r'\((\d{4})\)', clean_title)
    if parentheses_year:
        year = parentheses_year.group(1)
        clean_title = re.sub(r'\s*\(\d{4}\)\s*', ' ', clean_title).strip()
    else:
        current_year = datetime.datetime.now().year
        year_matches = re.findall(r'(?:^|[^0-9])(\d{4})(?:[^0-9]|$)', clean_title)
        if year_matches:
            for potential_year in year_matches:
                year_int = int(potential_year)
                if 1900 <= year_int <= current_year + 5:
                    year = potential_year
            if year_matches[0] == year and re.match(r'^' + year + r'[^0-9]', clean_title):
                if len(year_matches) > 1:
                    for potential_year in year_matches[1:]:
                        year_int = int(potential_year)
                        if 1900 <= year_int <= current_year + 5:
                            year = potential_year
                            break
                else:
                    year = None
    # Remove trailing season/volume number if not a known numbered show
    if year and re.search(r'\b\d+$', clean_title):
        known_numbered = [
            r'^24$', r'^9-1-1(\s|$)', r'^60\s?Minutes', r'^90\s?Day\s?Fianc[eé]'
        ]
        if not any(re.match(pat, clean_title, re.IGNORECASE) for pat in known_numbered):
            clean_title = re.sub(r'\b\d+$', '', clean_title).strip()
    if year and not re.match(r'^' + year + r'[^0-9]', clean_title):
        clean_title = re.sub(r'\.?' + year + r'\.?', ' ', clean_title)
    # Apply all shared cleaning patterns
    for pattern in patterns_to_remove:
        clean_title = re.sub(pattern, ' ', clean_title)
    clean_title = clean_title.strip()
    if not clean_title:
        clean_title = folder_name
    return clean_title, year

def get_content_type(folder_name):
    folder_lower = folder_name.lower()
    if re.search(r'season|episode|s\d+e\d+|complete series|tv series', folder_lower):
        return "TV Series"
    if re.search(r'[s](\d{1,2})[e](\d{1,2})', folder_lower):
        return "TV Series"
    anime_indicators = [
        r'anime', r'subbed', r'dubbed', r'\[jp\]', r'\[jpn\]', r'ova\b',
        r'ova\d+', r'アニメ', r'japanese animation'
    ]
    for indicator in anime_indicators:
        if re.search(indicator, folder_lower, re.IGNORECASE):
            # If it's anime and looks like a series, return Anime Series
            if re.search(r'season|episode|s\d+e\d+|complete series|tv series', folder_lower):
                return "Anime Series"
            return "Anime Movie"
    return "Unknown"

SCANNER_FILES = {
    "Anime Movie": "anime_movies.txt",
    "Anime Series": "anime_series.txt",
    "Movie": "movies.txt",
    "TV Series": "tv_series.txt",
    "Wrestling": "wrestling.txt"
}

def load_scanner_list(content_type):
    scanner_file = SCANNER_FILES.get(content_type)
    if not scanner_file:
        return []
    scanner_path = os.path.join("scanners", scanner_file)
    if not os.path.exists(scanner_path):
        return []
    with open(scanner_path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def _split_words(text):
    return set(re.findall(r'\w+', text.lower()))

def partial_scanner_match(search_term, scanner_title, min_overlap=1):
    search_words = _split_words(search_term)
    scanner_words = _split_words(scanner_title)
    overlap = search_words & scanner_words
    return len(overlap) >= min_overlap

def find_scanner_matches(search_term, content_type, year=None, threshold=0.75):
    """
    Return a list of scanner matches that closely match the search_term and year.
    Uses normalization and a weighted scoring system.
    """
    scanner_file = SCANNER_FILES.get(content_type, "movies.txt")
    scanners_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
    scanner_path = os.path.join(scanners_dir, scanner_file)
    matches = []

    if not os.path.exists(scanner_path):
        return matches

    norm_search = normalize_title(search_term)
    best_score = 0
    best_match = None

    # Helper to get word set without "&"
    def words_wo_and(text):
        return set(w for w in text.split() if w != "&")

    with open(scanner_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Extract title, year, and TMDB ID
            match = re.match(r'^(.+?)(?:\s+\((\d{4})\))?(?:\s+\[tmdb-(\d+)\])?$', line)
            if not match:
                continue
            scan_title = match.group(1).strip()
            scan_year = match.group(2)
            scan_tmdb = match.group(3)
            norm_scan = normalize_title(scan_title)

            score = 0
            # Exact title and year match
            if norm_search == norm_scan and (not year or (scan_year and str(year) == scan_year)):
                score = 100
            # Exact title match, year mismatch or missing
            elif norm_search == norm_scan:
                # For TV Series, ignore year mismatch
                if content_type == "TV Series":
                    score = 100
                elif not year or (scan_year and str(year) == scan_year):
                    score = 100
                else:
                    score = 90
            # Partial match (all words in search are in scanner title, ignoring "&")
            elif words_wo_and(norm_search) == words_wo_and(norm_scan):
                score = 80
            # Partial match (all words in search are in scanner title)
            elif set(norm_search.split()).issubset(set(norm_scan.split())):
                score = 70
            # Fuzzy/partial overlap
            elif partial_scanner_match(norm_search, norm_scan, min_overlap=2):
                score = 50

            if score > best_score:
                best_score = score
                best_match = {
                    "line": line,
                    "title": scan_title,
                    "year": scan_year,
                    "tmdb_id": scan_tmdb,
                    "score": score
                }

    if best_match:
        matches.append(best_match)
    return matches

def get_movie_folder_name(title, year, tmdb_id):
    if TMDB_FOLDER_ID and tmdb_id:
        return f"{title} ({year}) [tmdb-{tmdb_id}]"
    else:
        return f"{title} ({year})"

def get_series_folder_name(title, year, tmdb_id, season_number):
    if TMDB_FOLDER_ID and tmdb_id:
        base = f"{title} ({year}) [tmdb-{tmdb_id}]"
    else:
        base = f"{title} ({year})"
    return os.path.join(base, f"S{season_number:02d}")

def _extract_folder_metadata(folder_name):
    clean_title = folder_name  # Only assign once

    # Remove SxxExx or sxxexx patterns (season/episode)
    clean_title = re.sub(r'\b[Ss](\d{1,2})[Ee](\d{1,2})\b', '', clean_title)

    # Remove release group and bracketed tags at the end
    clean_title = re.sub(r'[-\s\[]?[A-ZaZ0-9]+(\[.*\])?$', '', clean_title)

    # Remove quality, codecs, etc.
    patterns_to_remove = [
        r'(?i)\b(720p|1080p|2160p|480p|576p|4K|UHD|HD|FHD|QHD)\b',
        r'(?i)\b(BluRay|BDRip|WEBRip|WEB-DL|HDRip|DVDRip|HDTV|DVD|REMUX)\b',
        r'(?i)\b(x264|x265|h264|h265|HEVC|AVC|AAC|AC3|DTS|TrueHD|Atmos|5\.1|7\.1|2\.0|10bit|8bit)\b',
        r'(?i)\b(AMZN|NF|DSNP|MeGusta|YIFY|RARBG|EVO|NTG|YTS|SPARKS|GHOST|SCREAM|ExKinoRay|EZTVx)\b',
        r'\[.*?\]',  # Remove anything in brackets
    ]
    for pattern in patterns_to_remove:
        clean_title = re.sub(pattern, '', clean_title)

    # Replace dots, underscores, and dashes with spaces
    clean_title = re.sub(r'[._\-]+', ' ', clean_title)
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    return clean_title

def normalize_unicode(text):
    """Normalize unicode characters to closest ASCII equivalent."""
    if not isinstance(text, str):
        return text
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')

def normalize_title(title):
    # Remove all punctuation (including !, ?, ., etc.)
    title = re.sub(r'[^\w\s]', '', title)
    # Normalize unicode (remove accents), lowercase, and strip
    title = normalize_unicode(title)
    title = title.lower().strip()
    # Collapse whitespace
    title = re.sub(r'\s+', ' ', title)
    return title
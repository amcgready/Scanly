import re
import datetime
import unicodedata
import os
import difflib

def extract_folder_metadata(folder_name):
    # ...copy the logic from DirectoryProcessor._extract_folder_metadata...
    # (Use the latest, most correct version)
    title = folder_name
    year = None
    parentheses_year = re.search(r'\((\d{4})\)', folder_name)
    if parentheses_year:
        year = parentheses_year.group(1)
        clean_title = re.sub(r'\s*\(\d{4}\)\s*', ' ', folder_name).strip()
    else:
        current_year = datetime.datetime.now().year
        year_matches = re.findall(r'(?:^|[^0-9])(\d{4})(?:[^0-9]|$)', folder_name)
        clean_title = folder_name
        if year_matches:
            for potential_year in year_matches:
                year_int = int(potential_year)
                if 1900 <= year_int <= current_year + 5:
                    year = potential_year
            if year_matches[0] == year and re.match(r'^' + year + r'[^0-9]', folder_name):
                if len(year_matches) > 1:
                    for potential_year in year_matches[1:]:
                        year_int = int(potential_year)
                        if 1900 <= year_int <= current_year + 5:
                            year = potential_year
                            break
                else:
                    year = None
    clean_title = folder_name
    if year and not re.match(r'^' + year + r'[^0-9]', folder_name):
        clean_title = re.sub(r'\.?' + year + r'\.?', ' ', clean_title)
    patterns_to_remove = [
        r'(?i)\b(720p|1080p|1440p|2160p|4320p|480p|576p|8K|4K|UHD|HD|FHD|QHD)\b',
        r'(?i)\b(BluRay|Blu Ray|Blu-ray|BD|REMUX|BDRemux|BDRip|DVDRip|HDTV|WebRip|WEB-DL|WEBRip|Web|HDRip|DVD|DVDR)\b',
        r'(?i)\b(xvid|divx|x264|x265|hevc|h264|h265|HEVC|avc|vp9|av1)\b',
        r'(?i)\b(DTS[-\.]?(HD|ES|X)?|DD5\.1|AAC|AC3|TrueHD|Atmos|MA|5\.1|7\.1|2\.0|opus)\b',
        r'(?i)(\[.*?\]|\-[a-zA-Z0-9_]+$)',
        r'(?i)\b(AMZN|EfficientNeatChachalacaOfOpportunityTGx|SPRiNTER|KRaLiMaRKo|DVT|TheEqualizer|YIFY|NTG|YTS|SPARKS|RARBG|EVO|GHOST|HDCAM|CAM|TS|SCREAM|ExKinoRay)\b',
        r'(?i)\b(HDR|VC|10bit|8bit|Hi10P|IMAX|PROPER|REPACK|HYBRID|DV)\b'
    ]
    for pattern in patterns_to_remove:
        clean_title = re.sub(pattern, ' ', clean_title)
    clean_title = re.sub(r'\.|\-|_', ' ', clean_title)
    clean_title = re.sub(r'\bFGT\b', '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'\(\s*\)', '', clean_title)  # Remove empty parentheses
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
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

def normalize_title(title):
    # Replace dots and underscores with spaces, remove extra spaces, lowercase
    return re.sub(r'[\W_]+', ' ', title).strip().lower()

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
    Uses normalization and partial word overlap.
    """
    scanner_file = SCANNER_FILES.get(content_type, "movies.txt")
    scanners_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
    scanner_path = os.path.join(scanners_dir, scanner_file)
    matches = []

    if not os.path.exists(scanner_path):
        return matches

    norm_search = normalize_title(search_term)

    with open(scanner_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^(.+?)(?:\s+\((\d{4})\))?(?:\s+\[tmdb-\d+\])?$', line)
            if not match:
                continue
            scan_title = match.group(1).strip()
            scan_year = match.group(2)
            # DEBUG: Print what we're comparing
            print(f"Comparing: '{search_term}' (year={year}) vs '{scan_title}' (year={scan_year})")
            if partial_scanner_match(search_term, scan_title) or normalize_title(search_term) in normalize_title(scan_title):
                if year and scan_year and str(year) != str(scan_year):
                    continue
                matches.append(line)
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
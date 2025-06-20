import re
import datetime

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
            return "Anime"
    return "Unknown"
patterns_to_remove = [
    # years
    r'\b(19|20)\d{2}\b', 
    # video quality and formats
    r'(?i)\b(2160p|1080p|720p|480p|576p|4k|Theatrical Cut|Theateatrical\.Cut|H.\265|uhd|hdr10|Atvp|Web-DL|H\.264|HDR|hd|Web|hd master|Hybrid|Remaster|plus|remux|bluray|BDRemux|blu-ray|web-dl|webdl|webrip|hdrip|dvdrip|hdtv|x264|x265|h264|h265|hevc|avc|extended|uncut|proper|repack|limited|internal|complete|season|s\d{1,2}e\d{1,2}|s\d{1,2}|e\d{1,2}|part\s?\d+|cd\d+|disc\d+|disk\d+|episode|ep\d+|vol\d+|volume|boxset|collection|special|edition|director.?s.?cut|criterion|imax|theatrical|remastered|restored|uncensored|unrated|bdrip|brrip|dvdscr|r5|cam|ts|tc|scr|workprint|sample|read.?nfo|nfo)\b',
    # audio patterns (expanded for channels like AAC2, AAC2.0, DDP5, etc.)
    r'(?i)\b(DD5\.1|MA|DDP5(\.\d)?|FLAC|AAC(\d(\.\d)?)?|AC3|DTS|TrueHD|Atmos|DV|1\.0|2\.0|5\.1|7\.1|10bit|8bit|opus|dual|audio)\b',
    # language patterns
    r'(?i)\b(eng|english|fr|fre|french|spa|es|spanish|ita|it|italian|ger|de|german|rus|ru|russian|jpn|ja|japanese|chi|zh|chinese|kor|ko|korean|nl|dut|dutch|por|pt|portuguese|pl|pol|polish|cz|cze|czech|hun|magyar|gre|ell|greek|tur|tr|turkish|arabic|ara|heb|he|hebrew|ind|id|indonesian|tha|th|thai|vie|vi|vietnamese|fil|tl|tagalog|malay|tam|ta|tamil|tel|te|telugu|kan|kn|kannada|ben|bn|bengali|mar|mr|marathi|guj|gu|gujarati|pun|pa|punjabi|ori|or|odia|mal|ml|malayalam|bur|my|burmese|khm|km|khmer|lao|lo|lao|mon|mn|mongolian|nep|ne|nepali|sin|si|sinhala|swa|sw|swahili|tgl|tl|tagalog|uzb|uz|uzbek|yor|yo|yoruba|zho|zh|chinese)\b',
    # subtitle/subbed patterns
    r'(?i)\b(subbed|ensubbed|engsub|engsubbed|sub|subs|subtitles|withsubs|withsubtitles)\b',
    # release groups and tags
    r'(?i)\b(rarbg|yify|kuchu|evo|ntg|EniaHD|spark|ghost|nodlabs|EfficientNeatChachalacaOfOpportunity|scream|Theequalizer|Framestor|exkinoray|Sprinter|Rumour|Phobos|Zq|Bobropandavar|Kralimarko|seleZen|eztvx|ntb|tgx|fgt|tepes|usury|bipolar|epsilon|dvt|edge2020|master5i|yts\.mx|fgt|flux|leGi0n|apfelstrudel|ben\.the\.men|ben|the|men|ster|team|group|mux|rip|raw)\b',
    # season and episode formats
    r'(?i)\b(S\d{1,2}E\d{1,2}|S\d{1,2}|E\d{1,2}|Season\s?\d+|Episode\s?\d+)\b',
    # disc and volume formats
    r'(?i)\b(CD\d+|Disc\d+|Disk\d+|Part\s?\d+|Vol\.?\d+|Volume|Episode|Ep\d+)\b',
    # punctuation
    r'[\[\]\(\)\{\}\-_\.\,]', 
    # extra spaces
    r'\s+',
    # standalone patterns
    r'(?i)\bcut\b',
    r'(?i)h[\.\s]?265',  # Matches "H.265", "H 265", "H265"
    # remove leftover single numbers (likely from channels)
    r'(?i)\b\d\b',
]
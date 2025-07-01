import re

patterns_to_remove = [
    #years
    re.compile(r'\b(19|20)\d{2}\b', re.IGNORECASE), 
    # video quality and formats
    re.compile(r'\b(2160p|1080p|720p|480p|576p|4k|uhd|hdr10|plus|remux|bluray|BDRemux|blu-ray|web-dl|webdl|webrip|hdrip|dvdrip|hdtv|x264|x265|h264|h265|hevc|avc|aac|ac3|dts|truehd|atmos|5\.1|7\.1|2\.0|10bit|8bit|dv|ma|ddp5|subs?|multi|dubbed|latino|castellano|hindi|fre|ita|hun|rus|cze|eng|french|german|spanish|japanese|russian|chinese|korean|nl|ita|pt|por|tur|swesub|nordic|norwegian|danish|finnish|swedish|nor|fin|swe|dk|subbed|dubbed|dual|audio|extended|uncut|proper|repack|limited|internal|complete|season|s\d{1,2}e\d{1,2}|s\d{1,2}|e\d{1,2}|part\s?\d+|cd\d+|disc\d+|disk\d+|episode|ep\d+|vol\d+|volume|boxset|collection|special|edition|director.?s.?cut|criterion|imax|theatrical|remastered|restored|uncensored|unrated|bdrip|brrip|dvdscr|r5|cam|ts|tc|scr|workprint|sample|read.?nfo|nfo)\b', re.IGNORECASE),
    # release groups and tags
    re.compile(r'\b(rarbg|yify|evo|ntg|spark|ghost|nodlabs|scream|exkinoray|eztvx|ntb|tgx|fgt|tepes|usury|bipolar|epsilon|dvt|edge2020|master5i|yts\.mx|fgt|flux|leGi0n|apfelstrudel|ben\.the\.men|ben|the|men|ster|team|group|subs|dub|mux|rip|raw|eng|fra|ita|spa|ger|rus|jpn|chi|kor|nl|por|pl|cz|hun|gre|tur|arabic|heb|ind|tha|vie|fil|malay|tam|tel|kan|ben|mar|guj|pun|ori|mal|bur|khm|lao|mon|nep|sin|swa|tgl|uzb|vie|yor|zho)\b', re.IGNORECASE),
    # season and episode formats
    re.compile(r'\b(S\d{1,2}E\d{1,2}|S\d{1,2}|E\d{1,2}|Season\s?\d+|Episode\s?\d+)\b', re.IGNORECASE),
    # disc and volume formats
    re.compile(r'\b(CD\d+|Disc\d+|Disk\d+|Part\s?\d+|Vol\.?\d+|Volume|Episode|Ep\d+)\b', re.IGNORECASE),
    #punctuation
    re.compile(r'[\[\]\(\)\{\}\-_\.\,]', re.IGNORECASE), 
    # extra spaces
    re.compile(r'\s+', re.IGNORECASE),
]
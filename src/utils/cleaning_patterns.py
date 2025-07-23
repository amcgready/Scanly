patterns_to_remove = [
    # years
    r'\b(19|20)\d{2}\b',
    # Remove everything after SxxExx (season/episode) pattern, including the episode code itself
    r'(?i)\bS\d{1,2}E\d{1,2}\b.*',
    # Remove partial SxxE patterns (season/episode), including S01E, S1E
    r'(?i)\bS\d{1,2}E(\d{0,2})\b',
    # Remove "Season #-#" or "Seasons #-#" (e.g. "Season 1-18", "Seasons 2-5", "S01-03")
    r'(?i)\bS(eason)?s?\s?\d{1,2}\s?-\s?\d{1,2}\b',
    # Remove language track counts like 2xUKR, 3xENG, etc.
    r'(?i)\b\d+x[a-z]{2,4}\b',
    # video quality and formats
    r'(?i)\b(2160p|1080p|Fhd|UHDremux|Ultrahd|Enhance|Animated|HONE|Multisub|TV|1080i|960p|DDR|DDPA5|DDP|Pal|Dubbed|Subbed|HD1080p|4K80|10-Bit|Hhweb|Subtitle|Extras|Language|P8|Web-D|TVShows|Rife\.4|HDR10Plus|Tvrip|DVD|F79|TV Series|Dolby Vision|6000nit|Ai upscale|Telesync|3840X2160|Orig|Re-Grade|Upscale|Atmos-MT|MULTI-RIFE|0-HDS|D.Web|DLRip|P5|4.25V2|60fps|SDR|Qhd|NF|SD|Webmux|master|ben\.the\.men|Classics|Sgf|HDR-X|v1|35mm|DD|Upscaled|Blue Ray|R2|Special.Assembly|AI|Multi|Kc|Extended\.Version|480|720|1080|2160|720p|480p|576p|4k|Theatrical Cut|Theateatrical\.Cut|uhd|hdr10|Atvp|Web-DL|HDR|hd|Web|hd master|Hybrid|Remaster|plus|remux|bluray|BDRemux|blu-ray|web-dl|webdl|webrip|hdrip|dvdrip|hdtv|x264|x265|h264|h265|hevc|avc|extended|uncut|proper|repack|limited|internal|complete|season|part\s?\d+|cd\d+|disc\d+|disk\d+|episode|ep\d+|vol\d+|volume|boxset|collection|special|specials|edition|director\.?s\.?cut|criterion|imax|theatrical|remastered|restored|uncensored|unrated|bdrip|brrip|dvdscr|r5|cam|ts|tc|scr|workprint|sample|read\.?nfo|nfo)\b',
    # Remove H.264, H 264, H264, H.265, H 265, H265 (with or without spaces/dots)
    r'(?i)\bH[\s\.]?26[45]\b',
    # video file formats (new pattern)
    r'(?i)\b(mkv|mp4|avi|mov|wmv|flv|m4v|ts|Mpeg2|Lpcm2|m2ts|webm|vob|mpg|mpeg|3gp|divx|xvid)\b',
    # audio patterns (expanded for channels like AAC2, AAC2.0, DDP5, etc.)
    r'(?i)\b(DD5\.1|FLAC-TTGA|FLAC2|Dolby|FLAC2.0|PCM|TTGA|MA|MA5\.1|EAC3|GP|SYNCOPY|H264-FT|AV1|G66|LC|VC-1|LPCM|5 1|1 0|2 0|VO|DDP2\.0|FLAC1\.0|H-264|H-265|DDP5(\.\d)?|FLAC|AAC(\d(\.\d)?)?|AC3|DTS|TrueHD|Atmos|DV|1\.0|2\.0|5\.1|7\.1|10bit|8bit|opus|dual|audio)\b',
    # language patterns
    r'(?i)\b(eng|pk|english|USA|Lang|Jrp|fr|le-production|fre|french|Ukr|Eng|Un|USA|Nuevo|R\.G\.|RG|R G|Mundo|Lat|spa|Ukr|Sk|es|Swedish|spanish|ita|it|italian|ger|de|german|rus|ru|russian|jpn|ja|japanese|chi|zh|chinese|kor|ko|korean|nl|dut|dutch|por|pt|portuguese|pl|pol|polish|cz|cze|czech|hun|magyar|gre|ell|greek|tur|tr|turkish|arabic|ara|heb|he|hebrew|ind|id|indonesian|tha|th|thai|vie|vi|vietnamese|fil|tl|tagalog|malay|tam|ta|tamil|tel|te|telugu|kan|kn|kannada|bn|bengali|mar|marathi|guj|gu|gujarati|pun|pa|punjabi|ori|or|odia|mal|ml|malayalam|bur|burmese|khm|km|khmer|lao|lo|lao|mon|mn|mongolian|nep|ne|nepali|si|swa|sw|swahili|tgl|tl|tagalog|uzb|uz|uzbek|yor|yo|yoruba|zho|zh|chinese)\b',
    # subtitle/subbed patterns
    r'(?i)\b(subbed|ensubbed|Bdc|Rmteam|Bcore|Pignus|Sbr|CAT|Esp|Jap|Latino|Hindi|engsub|DataLass|Eztv|Dovi Ace|RE|eztv\.re|TNClub|rutracker\.org|Iva|GalaxyRG265|YTS\.AG|3xRUS|Ingles|En|Es|engsubbed|sub|subs|subtitles|withsubs|withsubtitles)\b',
    # release groups and tags (improved: match before brackets, parenthesis, space, or end)
    r'(?i)\b(rarbg|xebec|br|Kbox|DoVi|Cinefile|Redblade|tarunk9c|Paperpirates|nogrp|3L|HDCLUB|Tdd|FaiLED|PrimeFix|Timecut|Phdteam|bordure|iah d|r0b0t|CondorFilmsStudio|AtmosDovi|Iris2|FW|mars|L0L|MZABI|zelka|SKGTV|STRiFE|thesickle|zigzag|newcomers|kovalski|zero00|varyg|cap\.201_220|sofcj|mem|sigla|sic|afm72|will1869|r00t|vietnam|oath|srs|hiqve|rudub\.tv|r\.g\.generalfilm|alexfilm|ultradox|drainedday|musicmadme|rawr|j363|cr|c3ntric|phocis|zechs|bd|nixon|idn_crew|n0ttz|trf|yg|lf|ion|casstudio|lazycunts|pootled|now web|truffle|telephiles|amcon|bae|yello|by wild_cat|bugsfunny|utr|playweb|p7|vff|by\.dvt|newstation|ndrecords|amb3r|baibako\.tv|gowa|rodziny|ft|bluraydd5|pgw|btn|d3g|hp8|mvo|lostfilm|omskbird|hone|wdym|bs|rgzsrutracker|galaxytv|no-dnr|alekartem|monolith|bone|full4movies|tardis|don|rempown|taoe|phoenix|pmtp|nosivid|hmax|dd2\.0|squalor|trollhd|ajp69|edith|opus51|cairn|phr0sty|garshasp|boxedpotatoes|lazy|aoc|deflate|thebiscuitman|yellowbird|kyle|hurtom|trolluhd|repulse|smurf|dima_2004|dima|toloka\.to|silence|ggez|shortbrehd|ggwp|i_c|avc|zerobuild|pir8|theblackking|cakes|mixed|eztv\.re|by aktep|edge|protonmovies|redrussian1337|ctrlhd|hdhweb|sigma|teamhd|megusta|pack|aptv|hdo|dlmux|kings|lektor|rartv|lektor pl|alusia|successfulcrab|eztvx\.to|dc|triton|p8\.by\.dvt|sicfoi|dimepiece|spooks|handjob|johny4545|master5|huzzah|nahom|alfahd|collective|yts\.lt|cc|criterion|nnmclub|tcv|yify|pirates|snake|cinephiles|cmrg|dvsux|ethd|tigole|swtyblz|shitrips|secrecy|warui|cyber|sartre|rutracker|roland|roccat|kogi|accomplishedyak|pianyuan|trump|osm|ika|dirtyhippie|1080p_by_vedigo|artemix|mircrew|apex|triton|kuchu|datphyr|aki|dynamic|tekno3d|kaurismaki|finnish|dovi|lm|uhdreescalado|castellano|4k4u|evo|ntg|eniahd|spark|ghost|nodlabs|efficientneatchachalacaofopportunity|scream|theequalizer|framestor|exkinoray|sprinter|rumour|phobos|zq|bobropandavar|kralimarko|selezen|eztvx|ntb|tgx|fgt|tepes|usury|bipolar|epsilon|dvt|edge2020|master5i|yts\.mx|fgt|flux|leGi0n|apfelstrudel|ster|team|group|mux|rip|raw|panda)\b(?=[\[\(\{\)\]\s\.]|$)',
    # production/distribution companies
    r'(?i)\b(sony[\s\._-]*pictures|ANZM|Gi6|TBS|Tommy|Stan|Moviesbyrizzo|Zmnt|MrO|Esubs|3GB|MassModz|Hybryd|Gattopollo|Spamkings|Y2Flix|Full|Ethel|Rcvr|Pcock|Pcok|Hulu|AMZN|DSNP|amazon|warner[\s\._-]*bros|universal[\s\._-]*pictures|paramount([\s\._-]*pictures)?|columbia[\s\._-]*pictures|20th[\s\._-]*century[\s\._-]*fox|fox[\s\._-]*searchlight|lionsgate|mgm|walt[\s\._-]*disney|disney|pixar|dreamworks|new[\s\._-]*line[\s\._-]*cinema|focus[\s\._-]*features|miramax|tristar|legendary|a24|blumhouse|amazon[\s\._-]*studios|netflix|hbo|max|apple[\s\._-]*tv|apple[\s\._-]*originals|bbc|canal\+|gaumont|pathe|studio[\s\._-]*ghibli|toho|shout[\s\._-]*factory|criterion)\b',
    # season and episode formats
    r'(?i)\b(S\d{1,2}E\d{1,2}|S\d{1,2}|E\d{1,2}|Season\s?\d+|Episode\s?\d+)\b',
    # disc and volume formats
    r'(?i)\b(CD\d+|Disc\d+|Disk\d+|Part\s?\d+|Vol\.?\d+|Volume|Episode|Ep\d+)\b',
    # punctuation
    r'[\[\]\(\)\{\}\-_\.\,+\*\/\\\|:;\"\'\?=~`!@#$%^&]+',
    # extra spaces
    r'\s+',
    # standalone patterns
    r'(?i)\bcut\b',
    # trailing group tags at end (expand as needed)
    r'\s+(Ctrlhd|JATT|DB|SiCFoI|As76-Ft|As76|Bigdoc|Dimepiece|Spooks|HANDJOB|johny4545|Master5|Huzzah|Nahom|Alfahd|Collective|YTS\.LT|CC|Criterion|NNMClub|TCV|yify|pirates|snake|Cinephiles|CMRG|DVSUX|Nogrp|Ethd|Tigole|Swtyblz|Shitrips|Secrecy|Warui|Cyber|Sartre|Rutracker|Roland|Roccat|Kogi|Accomplishedyak|Pianyuan|Trump|OSM|ika|DirtyHippie|1080p_by_vedigo|Artemix|Mircrew|APEX|Triton|kuchu|Datphyr|Aki|Dynamic|Tekno3d|Kaurismaki|Finnish|Dovi|Lm|UHDreescalado|Castellano|4k4U|evo|ntg|EniaHD|spark|ghost|nodlabs|EfficientNeatChachalacaOfOpportunity|scream|Theequalizer|Framestor|exkinoray|Sprinter|Rumour|Phobos|Zq|Bobropandavar|Kralimarko|seleZen|eztvx|ntb|tgx|fgt|tepes|usury|bipolar|epsilon|dvt|edge2020|master5i|yts\.mx|fgt|flux|leGi0n|apfelstrudel|ster|team|group|mux|rip|raw|Panda)$',
    # Remove lone season number at end (e.g. "American Dad 1")
    r'(?<=\s)\d{1,2}$',
    # Remove file size patterns like 193GB, 12Gb, 1TB, etc.
    r'\b\d+\s?(GB|G[Bb]|MB|M[Bb]|TB|T[Bb])\b',
    # Remove the word "Series" if it appears after the title
    r'(?i)\bseries\b',
    # Remove actor names in parentheses (e.g., (Ted Danson - Shelley Long - Kirstie Alley))
    r'\([^)]+\)',
    # Remove common non-title phrases (customize as needed)
    r'(?i)\b(stacja kosmiczna|lektor pl|napisy pl|polska wersja|wersja pl|Głowa)\b',
]

case_sensitive_patterns = [
    r'\bRiCK\b', r'\bGoldenBridge\b', r'\bJySzE\b',r'\bJPBD\b', r'\bby AKTEP\b', r'\bBIGDOC\b', r'\bAS76\b', r'\bSHD13\b', r'\bSiQ\b', r'\bSunabouzu\b',
    r'\bsinhala\b', r'\bUS\b', r'\bLostFIlm\b', r'\bBaibaKo\b', r'\bCARVED\b', r'\bRuDub\b', r'\bGHOSTS\b',
    r'\bGeneralfilm\b', r'\biAHD\b', r'\bDB\b', r'\bHONE\b', r'\bRGzsRutracker\b', r'\bFLUX\b', r'\biris2\b',
    r'\bh265\b', r'\bACE\b', r'\bsbor\b', r'\b264-PIX\b', r'\bMOREBiTS\b', r'\bTorrent911.lol\b',
    r'\bTorrent911.wf\b', r'\bKAZETV\b', r'\bteneighty\b', r'\bDatte13\b', r'\bsam\b',r'\bHi10\b', r'\bRaptoR\b', r'\b6D3D30BF\b', r'\bDFD9BD67\b', r'\bT3KASHi\b',r'\bBD\b', r'\bBeanosubs\b',r'\bPikanet128\b', r'\bArid\b', r'\bwww.UIndex.org\b',r'\bwww.Torrenting.com\b',r'\bBEST TORRENTS COM\b', r'\bEx torrenty org\b', r'\bRalf\b',
]
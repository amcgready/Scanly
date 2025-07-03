patterns_to_remove = [
    # years
    r'\b(19|20)\d{2}\b',
    # Remove everything after SxxExx (season/episode) pattern, including the episode code itself
    r'(?i)\bS\d{1,2}E\d{1,2}\b.*',
    # Remove partial SxxE patterns (season/episode), including S01E, S1E
    r'(?i)\bS\d{1,2}E(\d{0,2})\b',
    # Remove "Season #-#" or "Seasons #-#" (e.g. "Season 1-18", "Seasons 2-5")
    r'(?i)\bSeasons?\s?\d{1,2}\s?-\s?\d{1,2}\b',
    # Remove language track counts like 2xUKR, 3xENG, etc.
    r'(?i)\b\d+x[a-z]{2,4}\b',
    # video quality and formats
    r'(?i)\b(2160p|1080p|1080i|DDR|DDP|Pal|Dubbed|Subbed|HD1080p|4K80|10-Bit|Hhweb|Subtitle|Extras|Language|P8|Web-D|TVShows|Rife\.4|HDR10Plus|Seasons|Tvrip|DVD|F79|TV Series|Dolby Vision|6000nit|Ai upscale|Telesync|3840X2160|Orig|Re-Grade|Upscale|Atmos-MT|MULTI-RIFE|0-HDS|D.Web|DLRip|P5|4.25V2|60fps|SDR|Qhd|NF|SD|Webmux|master|ben\.the\.men|Classics|Sgf|HDR-X|v1|35mm|DD|Upscaled|Blue Ray|R2|Special.Assembly|AI|Multi|Kc|Extended\.Version|480|720|1080|2160|720p|480p|576p|4k|Theatrical Cut|Theateatrical\.Cut|uhd|hdr10|Atvp|Web-DL|HDR|hd|Web|hd master|Hybrid|Remaster|plus|remux|bluray|BDRemux|blu-ray|web-dl|webdl|webrip|hdrip|dvdrip|hdtv|x264|x265|h264|h265|hevc|avc|extended|uncut|proper|repack|limited|internal|complete|season|part\s?\d+|cd\d+|disc\d+|disk\d+|episode|ep\d+|vol\d+|volume|boxset|collection|special|specials|edition|director\.?s\.?cut|criterion|imax|theatrical|remastered|restored|uncensored|unrated|bdrip|brrip|dvdscr|r5|cam|ts|tc|scr|workprint|sample|read\.?nfo|nfo)\b',
    # Remove H.264, H 264, H264, H.265, H 265, H265 (with or without spaces/dots)
    r'(?i)\bH[\s\.]?26[45]\b',
    # video file formats (new pattern)
    r'(?i)\b(mkv|mp4|avi|mov|wmv|flv|m4v|ts|Mpeg2|Lpcm2|m2ts|webm|vob|mpg|mpeg|3gp|divx|xvid)\b',
    # audio patterns (expanded for channels like AAC2, AAC2.0, DDP5, etc.)
    r'(?i)\b(DD5\.1|MA|MA5\.1|EAC3|GP|SYNCOPY|H264-FT|AV1|G66|LC|VC-1|LPCM|5 1|1 0|2 0|VO|DDP2\.0|FLAC1\.0|H-264|H-265|DDP5(\.\d)?|FLAC|AAC(\d(\.\d)?)?|AC3|DTS|TrueHD|Atmos|DV|1\.0|2\.0|5\.1|7\.1|10bit|8bit|opus|dual|audio)\b',
    # language patterns
    r'(?i)\b(eng|pk|english|USA|fr|fre|french|Hin|Un|US|Nuevo|Mundo|Lat|spa|Ukr|Sk|es|Swedish|spanish|ita|it|italian|ger|de|german|rus|ru|russian|jpn|ja|japanese|chi|zh|chinese|kor|ko|korean|nl|dut|dutch|por|pt|portuguese|pl|pol|polish|cz|cze|czech|hun|magyar|gre|ell|greek|tur|tr|turkish|arabic|ara|heb|he|hebrew|ind|id|indonesian|tha|th|thai|vie|vi|vietnamese|fil|tl|tagalog|malay|tam|ta|tamil|tel|te|telugu|kan|kn|kannada|bn|bengali|mar|mr|marathi|guj|gu|gujarati|pun|pa|punjabi|ori|or|odia|mal|ml|malayalam|bur|my|burmese|khm|km|khmer|lao|lo|lao|mon|mn|mongolian|nep|ne|nepali|sin|si|sinhala|swa|sw|swahili|tgl|tl|tagalog|uzb|uz|uzbek|yor|yo|yoruba|zho|zh|chinese)\b',
    # subtitle/subbed patterns
    r'(?i)\b(subbed|ensubbed|CAT|Esp|Jap|Latino|Hindi|engsub|DataLass|Iva|GalaxyRG265|YTS\.AG|3xRUS|Ingles|En|Es|engsubbed|sub|subs|subtitles|withsubs|withsubtitles)\b',
    # release groups and tags
    r'(?i)\b(rarbg|Xebec|br|Varyg|afm72|Will1869|r00t|ViETNAM|Oath|SRS|HiQVE|RuDub\.tv|R\.G\.Generalfilm|Alexfilm|Ultradox|DrainedDay|MusicMadMe|Rawr|J363|Cr|C3Ntric|PHOCiS|ZECHS|Bd|Nixon|iDN_Crew|N0TTZ|TRF|YG|LF|Ion|CasStudio|Lazycunts|Pootled|NOW WEB|Truffle|Telephiles|AMCON|Bae|Yello|By Wild_cat|Bugsfunny|UTR|Playweb|P7|Vff|by\.DVT|NewStation|NDRecords|Amb3r|Baibako\.tv|Gowa|Rodziny|Ft|BlurayDD5|PGW|BTN|D3G|HP8|MVO|Lostfilm|Omskbird|Hone|WDYM|BS|RGzsRuTracker|Galaxytv|no-DNR|Alekartem|Monolith|Bone|Full4Movies|Tardis|DON|Rempown|TAoE|Phoenix|Pmtp|Nosivid|HMAX|Dd2\.0|Squalor|Trollhd|AJP69|Edith|Opus51|Cairn|Phr0sty|Garshasp|Boxedpotatoes|Lazy|AOC|Deflate|Thebiscuitman|Yellowbird|Kyle|Hurtom|TrollUHD|Repulse|Smurf|Dima_2004|Dima|Toloka\.TO|Silence|Ggez|Shortbrehd|Ggwp|i_c|avc|Zerobuild|pir8|Theblackking|Cakes|Mixed|Eztv\.re|by AKTEP|Edge|ProtonMovies|Redrussian1337|CtrlHD|Hdhweb|Sigma|Teamhd|Megusta|Pack|Aptv|HDO|DLMux|Kings|Lektor|Rartv|Lektor PL|Alusia|Successfulcrab|EZTVx\.to|DC|TRiToN|P8\.by\.DVT|SiCFoI|Dimepiece|Spooks|HANDJOB|johny4545|Master5|Huzzah|Nahom|Alfahd|Collective|YTS\.LT|CC|Criterion|NNMClub|TCV|yify|pirates|snake|Cinephiles|CMRG|DVSUX|Nogrp|Ethd|Tigole|Swtyblz|Shitrips|Secrecy|Warui|Cyber|Sartre|Rutracker|Roland|Roccat|Kogi|Accomplishedyak|Pianyuan|Trump|OSM|ika|DirtyHippie|1080p_by_vedigo|Artemix|Mircrew|APEX|Triton|kuchu|Datphyr|Aki|Dynamic|Tekno3d|Kaurismaki|Finnish|Dovi|Lm|UHDreescalado|Castellano|4k4U|evo|ntg|EniaHD|spark|ghost|nodlabs|EfficientNeatChachalacaOfOpportunity|scream|Theequalizer|Framestor|exkinoray|Sprinter|Rumour|Phobos|Zq|Bobropandavar|Kralimarko|seleZen|eztvx|ntb|tgx|fgt|tepes|usury|bipolar|epsilon|dvt|edge2020|master5i|yts\.mx|fgt|flux|leGi0n|apfelstrudel|ster|team|group|mux|rip|raw)\b',
    # production/distribution companies
    r'(?i)\b(sony[\s\._-]*pictures|Gi6|TBS|Tommy|Stan|Moviesbyrizzo|Zmnt|Esubs|3GB|MassModz|Hybryd|Gattopollo|Spamkings|Y2Flix|Full|Ethel|Rcvr|Pcock|Pcok|Hulu|AMZN|DSNP|amazon|warner[\s\._-]*bros|universal[\s\._-]*pictures|paramount([\s\._-]*pictures)?|columbia[\s\._-]*pictures|20th[\s\._-]*century[\s\._-]*fox|fox[\s\._-]*searchlight|lionsgate|mgm|walt[\s\._-]*disney|disney|pixar|dreamworks|new[\s\._-]*line[\s\._-]*cinema|focus[\s\._-]*features|miramax|tristar|legendary|a24|blumhouse|amazon[\s\._-]*studios|netflix|hbo|max|apple[\s\._-]*tv|apple[\s\._-]*originals|bbc|canal\+|gaumont|pathe|studio[\s\._-]*ghibli|toho|shout[\s\._-]*factory|criterion)\b',
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
    r'\s+(Ctrlhd|Rick|SiCFoI|As76-Ft|As76|Bigdoc|Dimepiece|Spooks|HANDJOB|johny4545|Master5|Huzzah|Nahom|Alfahd|Collective|YTS\.LT|CC|Criterion|NNMClub|TCV|yify|pirates|snake|Cinephiles|CMRG|DVSUX|Nogrp|Ethd|Tigole|Swtyblz|Shitrips|Secrecy|Warui|Cyber|Sartre|Rutracker|Roland|Roccat|Kogi|Accomplishedyak|Pianyuan|Trump|OSM|ika|DirtyHippie|1080p_by_vedigo|Artemix|Mircrew|APEX|Triton|kuchu|Datphyr|Aki|Dynamic|Tekno3d|Kaurismaki|Finnish|Dovi|Lm|UHDreescalado|Castellano|4k4U|evo|ntg|EniaHD|spark|ghost|nodlabs|EfficientNeatChachalacaOfOpportunity|scream|Theequalizer|Framestor|exkinoray|Sprinter|Rumour|Phobos|Zq|Bobropandavar|Kralimarko|seleZen|eztvx|ntb|tgx|fgt|tepes|usury|bipolar|epsilon|dvt|edge2020|master5i|yts\.mx|fgt|flux|leGi0n|apfelstrudel|ster|team|group|mux|rip|raw|Panda)$',
    # Remove lone season number at end (e.g. "American Dad 1")
    r'(?<=\s)\d{1,2}$',
    # Remove file size patterns like 193GB, 12Gb, 1TB, etc.
    r'\b\d+\s?(GB|G[Bb]|MB|M[Bb]|TB|T[Bb])\b',
    # Remove the word "Series" if it appears after the title
    r'(?i)\bseries\b',
    # Remove actor names in parentheses (e.g., (Ted Danson - Shelley Long - Kirstie Alley))
    r'\([^)]+\)',
]
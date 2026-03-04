"""Seed data for the mock YouTube Data API v3 server.

50 well-known tracks across rock, pop, indie, hip-hop, electronic.
20 artist channels. Pre-computed lowercase search index for rapidfuzz.
"""

TRACKS = [
    # Rock
    {"videoId": "mock_vid_001", "title": "Bohemian Rhapsody", "artist": "Queen", "duration_seconds": 355},
    {"videoId": "mock_vid_002", "title": "Stairway to Heaven", "artist": "Led Zeppelin", "duration_seconds": 482},
    {"videoId": "mock_vid_003", "title": "Hotel California", "artist": "Eagles", "duration_seconds": 391},
    {"videoId": "mock_vid_004", "title": "Smells Like Teen Spirit", "artist": "Nirvana", "duration_seconds": 301},
    {"videoId": "mock_vid_005", "title": "Back in Black", "artist": "AC/DC", "duration_seconds": 255},
    {"videoId": "mock_vid_006", "title": "Sweet Child O' Mine", "artist": "Guns N' Roses", "duration_seconds": 356},
    {"videoId": "mock_vid_007", "title": "Comfortably Numb", "artist": "Pink Floyd", "duration_seconds": 382},
    {"videoId": "mock_vid_008", "title": "Under the Bridge", "artist": "Red Hot Chili Peppers", "duration_seconds": 264},
    {"videoId": "mock_vid_009", "title": "Creep", "artist": "Radiohead", "duration_seconds": 236},
    {"videoId": "mock_vid_010", "title": "Everlong", "artist": "Foo Fighters", "duration_seconds": 250},
    # Pop
    {"videoId": "mock_vid_011", "title": "Billie Jean", "artist": "Michael Jackson", "duration_seconds": 294},
    {"videoId": "mock_vid_012", "title": "Like a Prayer", "artist": "Madonna", "duration_seconds": 340},
    {"videoId": "mock_vid_013", "title": "Rolling in the Deep", "artist": "Adele", "duration_seconds": 228},
    {"videoId": "mock_vid_014", "title": "Shape of You", "artist": "Ed Sheeran", "duration_seconds": 234},
    {"videoId": "mock_vid_015", "title": "Blinding Lights", "artist": "The Weeknd", "duration_seconds": 200},
    {"videoId": "mock_vid_016", "title": "Bad Guy", "artist": "Billie Eilish", "duration_seconds": 194},
    {"videoId": "mock_vid_017", "title": "Uptown Funk", "artist": "Bruno Mars", "duration_seconds": 270},
    {"videoId": "mock_vid_018", "title": "Shake It Off", "artist": "Taylor Swift", "duration_seconds": 219},
    {"videoId": "mock_vid_019", "title": "Levitating", "artist": "Dua Lipa", "duration_seconds": 203},
    {"videoId": "mock_vid_020", "title": "drivers license", "artist": "Olivia Rodrigo", "duration_seconds": 242},
    # Indie
    {"videoId": "mock_vid_021", "title": "Take Me Out", "artist": "Franz Ferdinand", "duration_seconds": 237},
    {"videoId": "mock_vid_022", "title": "Somebody That I Used to Know", "artist": "Gotye", "duration_seconds": 244},
    {"videoId": "mock_vid_023", "title": "Do I Wanna Know?", "artist": "Arctic Monkeys", "duration_seconds": 272},
    {"videoId": "mock_vid_024", "title": "Skinny Love", "artist": "Bon Iver", "duration_seconds": 229},
    {"videoId": "mock_vid_025", "title": "Electric Feel", "artist": "MGMT", "duration_seconds": 229},
    {"videoId": "mock_vid_026", "title": "Two Weeks", "artist": "Grizzly Bear", "duration_seconds": 244},
    {"videoId": "mock_vid_027", "title": "Mykonos", "artist": "Fleet Foxes", "duration_seconds": 266},
    {"videoId": "mock_vid_028", "title": "Oblivion", "artist": "Grimes", "duration_seconds": 244},
    {"videoId": "mock_vid_029", "title": "Motion Sickness", "artist": "Phoebe Bridgers", "duration_seconds": 232},
    {"videoId": "mock_vid_030", "title": "Heat Waves", "artist": "Glass Animals", "duration_seconds": 239},
    # Hip-Hop
    {"videoId": "mock_vid_031", "title": "Lose Yourself", "artist": "Eminem", "duration_seconds": 326},
    {"videoId": "mock_vid_032", "title": "HUMBLE.", "artist": "Kendrick Lamar", "duration_seconds": 177},
    {"videoId": "mock_vid_033", "title": "Sicko Mode", "artist": "Travis Scott", "duration_seconds": 312},
    {"videoId": "mock_vid_034", "title": "God's Plan", "artist": "Drake", "duration_seconds": 199},
    {"videoId": "mock_vid_035", "title": "Alright", "artist": "Kendrick Lamar", "duration_seconds": 219},
    {"videoId": "mock_vid_036", "title": "Juicy", "artist": "The Notorious B.I.G.", "duration_seconds": 319},
    {"videoId": "mock_vid_037", "title": "Runaway", "artist": "Kanye West", "duration_seconds": 547},
    {"videoId": "mock_vid_038", "title": "N.Y. State of Mind", "artist": "Nas", "duration_seconds": 293},
    {"videoId": "mock_vid_039", "title": "Ms. Jackson", "artist": "OutKast", "duration_seconds": 263},
    {"videoId": "mock_vid_040", "title": "Money Trees", "artist": "Kendrick Lamar", "duration_seconds": 386},
    # Electronic
    {"videoId": "mock_vid_041", "title": "Strobe", "artist": "deadmau5", "duration_seconds": 637},
    {"videoId": "mock_vid_042", "title": "Midnight City", "artist": "M83", "duration_seconds": 244},
    {"videoId": "mock_vid_043", "title": "Around the World", "artist": "Daft Punk", "duration_seconds": 429},
    {"videoId": "mock_vid_044", "title": "Scary Monsters and Nice Sprites", "artist": "Skrillex", "duration_seconds": 244},
    {"videoId": "mock_vid_045", "title": "Levels", "artist": "Avicii", "duration_seconds": 197},
    {"videoId": "mock_vid_046", "title": "Titanium", "artist": "David Guetta", "duration_seconds": 245},
    {"videoId": "mock_vid_047", "title": "Lean On", "artist": "Major Lazer", "duration_seconds": 176},
    {"videoId": "mock_vid_048", "title": "Faded", "artist": "Alan Walker", "duration_seconds": 212},
    {"videoId": "mock_vid_049", "title": "Don't You Worry Child", "artist": "Swedish House Mafia", "duration_seconds": 213},
    {"videoId": "mock_vid_050", "title": "Something About Us", "artist": "Daft Punk", "duration_seconds": 232},
]

CHANNELS = [
    {"channelId": "mock_ch_001", "title": "Queen Official"},
    {"channelId": "mock_ch_002", "title": "Led Zeppelin"},
    {"channelId": "mock_ch_003", "title": "Nirvana"},
    {"channelId": "mock_ch_004", "title": "Radiohead"},
    {"channelId": "mock_ch_005", "title": "Adele"},
    {"channelId": "mock_ch_006", "title": "Taylor Swift"},
    {"channelId": "mock_ch_007", "title": "The Weeknd"},
    {"channelId": "mock_ch_008", "title": "Billie Eilish"},
    {"channelId": "mock_ch_009", "title": "Arctic Monkeys"},
    {"channelId": "mock_ch_010", "title": "Kendrick Lamar"},
    {"channelId": "mock_ch_011", "title": "Drake"},
    {"channelId": "mock_ch_012", "title": "Daft Punk"},
    {"channelId": "mock_ch_013", "title": "Foo Fighters"},
    {"channelId": "mock_ch_014", "title": "Ed Sheeran"},
    {"channelId": "mock_ch_015", "title": "Eminem"},
    {"channelId": "mock_ch_016", "title": "Bon Iver"},
    {"channelId": "mock_ch_017", "title": "Glass Animals"},
    {"channelId": "mock_ch_018", "title": "Phoebe Bridgers"},
    {"channelId": "mock_ch_019", "title": "Olivia Rodrigo"},
    {"channelId": "mock_ch_020", "title": "Bruno Mars"},
]

# Pre-computed search index: lowercase "{title} {artist}" -> track/channel
TRACK_INDEX = []
for _t in TRACKS:
    TRACK_INDEX.append({
        "key": f"{_t['title']} {_t['artist']}".lower(),
        "track": _t,
    })

CHANNEL_INDEX = []
for _c in CHANNELS:
    CHANNEL_INDEX.append({
        "key": _c["title"].lower(),
        "channel": _c,
    })

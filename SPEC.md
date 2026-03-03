# spotify2youtube — Project Specification

## Overview

A Python Tkinter desktop application for migrating music metadata from Spotify to YouTube Music. The user connects both accounts upfront, browses their full Spotify library, selects and configures exactly what to transfer and how, then executes the migration — with manual fallback for ambiguous matches.

## Core Flow

### 1. Connect
- On first launch (or if credentials are missing), show a **Settings/Credentials screen** where the user enters:
  - **Spotify**: Client ID, Client Secret, Redirect URI (from Spotify Developer Dashboard)
  - **YouTube Music**: Path to `oauth.json` or trigger the `ytmusicapi` browser-based OAuth flow
- Credentials are saved to `credentials.json` in the project data directory (gitignored)
- Authenticate with Spotify via OAuth (using `spotipy`)
- Authenticate with YouTube Music via Google OAuth (using `ytmusicapi`)
- Both connections established before any browsing/transfer
- The Settings screen is re-accessible at any time via a [Settings] button to update credentials

### 2. Browse
- Fetch and display all available Spotify library data:
  - **Playlists** — name, description, track count, track list
  - **Liked Songs** — full saved tracks list
  - **Saved Albums** — album name, artist, track list
  - **Followed Artists** — artist name, genres
- Also fetch existing YouTube Music library for duplicate detection and merge targets

### 3. Select & Configure
Per-item controls:
- **Include/exclude** — checkboxes at every level (data type, playlist, individual track)
- **Rename** — change the target playlist/album name on YouTube Music
- **Reorder** — rearrange tracks within a playlist before transfer
- **Skip tracks** — deselect individual tracks within a selected playlist
- **Matching preference** — per-item strictness override (strict / fuzzy / manual)
- **Merge** — optionally merge into an existing YouTube Music playlist instead of creating a new one

### 4. Execute
- **Dry-run mode** — toggle before executing; simulates the full transfer without writing anything to YouTube Music. Shows what would be created, matched, skipped, and failed, so the user can review before committing.
- Transfer selected items with a progress indicator
- Auto-fuzzy matching for track lookup on YouTube Music
- Queue ambiguous/failed matches for manual resolution (step 5)
- Persist progress so transfer can be resumed if interrupted

### 5. Review & Resolve
- Summary of results: successful, skipped, failed, ambiguous
- For ambiguous/failed matches: present YouTube Music search results in the UI and let the user pick the correct match or skip
- Export a transfer report/log

## Persistence

Two separate JSON files, both gitignored:

- **`credentials.json`** — API keys, client secrets, OAuth tokens. Managed via the Settings UI. Never checked in.
- **`state.json`** — User selections, per-item configuration, transfer progress (what succeeded, what's pending). Enables closing the app and resuming later without re-selecting everything.

## Tech Stack

| Component        | Choice                                                      |
|------------------|-------------------------------------------------------------|
| Language         | Python                                                      |
| UI               | Tkinter                                                     |
| Spotify API      | `spotipy` (official Spotify Web API wrapper, OAuth)         |
| YouTube Music API| `ytmusicapi` (unofficial, Google OAuth / browser auth)      |
| State storage    | JSON file (human-readable, simple to debug)                 |
| Entry point      | `bin/` script or `python -m spotify2youtube`                |

## Track Matching Strategy

1. **Exact match** — search YouTube Music by track name + artist; accept if a single high-confidence result is returned
2. **Fuzzy match** — if no exact match, broaden the search (e.g., drop featured artists, try alternate spellings); accept the best result above a confidence threshold
3. **Manual fallback** — if no match clears the threshold, or if multiple candidates are equally plausible, queue the track for user resolution in the Review step. The user sees the Spotify track info alongside YouTube Music search results and picks the right one (or skips).

## UI Layout (High-Level)

### Settings / Credentials Screen
Shown on first launch or via [Settings] button. Fields for:
- Spotify Client ID, Client Secret, Redirect URI
- YouTube Music OAuth (trigger browser flow or point to existing `oauth.json`)
- [Test Connection] buttons for each service
- [Save] persists to `credentials.json`

```
┌──────────────────────────────────────────────────────────┐
│  spotify2youtube — Settings                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Spotify                                                 │
│  Client ID:     [________________________] [Test]        │
│  Client Secret: [________________________]               │
│  Redirect URI:  [________________________]               │
│                                                          │
│  YouTube Music                                           │
│  OAuth:         [Authenticate via Browser]  ✓ Connected  │
│                                                          │
│                          [Save & Continue]                │
└──────────────────────────────────────────────────────────┘
```

### Main Screen

```
┌──────────────────────────────────────────────────────────┐
│  spotify2youtube                              [Settings] │
├────────────┬─────────────────────────────────────────────┤
│            │                                             │
│  Spotify   │  Detail / Configuration Panel               │
│  Library   │                                             │
│  (tree)    │  - Shows contents of selected item          │
│            │  - Checkboxes for individual tracks          │
│  ☑ Playlists│  - Rename, reorder, merge controls          │
│    ☑ Road  │  - Matching preference dropdown              │
│    ☐ Chill │                                             │
│  ☑ Liked   │                                             │
│  ☑ Albums  │                                             │
│  ☐ Artists │                                             │
│            │                                             │
├────────────┴─────────────────────────────────────────────┤
│  ☐ Dry Run    [Transfer Selected]    Progress: ████░░ 67%│
│                                      23/34 items complete │
└──────────────────────────────────────────────────────────┘
```

## Decided

- **State format**: JSON — simple, human-readable, easy to debug
- **Podcasts**: Skipped entirely — not shown in the UI (no clean YT Music equivalent)
- **Collaborative playlists**: Transferred as regular playlists owned by the user
- **Rate limiting**: Throttle requests with exponential backoff; show estimated time remaining in the progress bar
- **Dry-run mode**: Checkbox in the bottom bar; runs the full matching/transfer logic but writes nothing to YouTube Music, showing a preview of results

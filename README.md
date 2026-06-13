# TMDB Inline Telegram Bot

A fast **Telegram inline bot** powered by **TMDB (The Movie Database)** that lets users search for **movies and TV shows directly inside any chat**.

Supports:

* Inline search (`@yourbot movie name`)
* Trending results when no query is entered
* Movie + TV search fallback logic
* Actor/person search support via `known_for`
* Pagination for large result sets
* Rich formatted results with:

  * Rating
  * Release date
  * Genres
  * Language
  * Country
  * Cast
  * Poster preview

---

## Features

### Inline Search

Search from anywhere on Telegram:

```text
@YourBot breaking bad
@YourBot interstellar
@YourBot dark
```

Returns:

* Movies
* TV Shows
* Actor searches mapped to their known works

Example:

```text
@YourBot shah rukh khan
```

Can return:

```text
Shah Rukh Khan • Dilwale Dulhania Le Jayenge
Shah Rukh Khan • My Name Is Khan
Shah Rukh Khan • Kal Ho Naa Ho
```

---

### Trending Feed

If no query is entered:

```text
@YourBot
```

Bot shows:

* Trending movies
* Trending TV shows

Using:

```text
/trending/all/day
```

---

### Smart Search Fallback

Search attempts happen in this order:

```text
/search/multi
↓
/search/movie
↓
/search/tv
↓
/trending/all/day
```

This prevents empty responses when TMDB search fails.

---

### Pagination

Supports Telegram inline pagination.

Shows:

```text
Showing 20 of 500 results
Showing 40 of 500 results
Showing 60 of 500 results
```

Uses:

```python
next_offset
```

and TMDB:

```text
?page=1
?page=2
?page=3
```

---

### Rich Movie Information

Each selected result sends:

```text
Movie / TV title
Year
Rating
Genres
Language
Country
Overview
Top Cast
Poster Preview
TMDB Link
```

Example:

```text
Interstellar (2014) • Movie

User Score ⭐️: 8.7 / 10

Release Date: 2014-11-05
Genres: #ScienceFiction #Drama #Adventure
Language: EN
Country of Origin: United States

Overview:
A team of explorers travel through a wormhole...

Cast:
Matthew McConaughey, Anne Hathaway...

Read More ...
```

---

## Installation

Clone repository:

```bash
git clone https://github.com/suhasa010/tmdbbbot.git
cd tmdbbbot
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Requirements

Python 3.11+

Libraries:

```text
python-telegram-bot
httpx
python-dotenv
asyncio
```

Install:

```bash
pip install python-telegram-bot httpx python-dotenv
```

---

## Environment Variables

Create `.env`

```env
BOT_TOKEN=telegram_bot_token
TMDB_TOKEN=tmdb_v4_bearer_token
TMDB_KEY=tmdb_api_key
```

Get TMDB credentials from:

[TMDB API Settings](https://www.themoviedb.org/settings/api?utm_source=chatgpt.com)

Get Telegram bot token from:

[BotFather](https://telegram.me/BotFather?utm_source=chatgpt.com)

---

## Running

```bash
python tmdbbbot.py
```

---

## Bot Commands

### Start

```text
/start
```

Shows help and usage instructions.

---

## Architecture

Main flow:

```text
Telegram Inline Query
        ↓
TMDB Search API
        ↓
Filter movie/tv/person
        ↓
Fetch detailed metadata
        ↓
Build formatted message
        ↓
Return Telegram inline results
```

---

## Caching

In-memory cache:

```python
QUERY_CACHE = {}
CACHE_TTL = 86400
```

Used for:

* Query results
* Pagination reuse
* Reducing TMDB API requests

---

## Rate Limiting

Concurrency controlled via:

```python
sem = asyncio.Semaphore(10)
```

Used to avoid excessive parallel requests.

---

## Known Issues

### Intermittent `ConnectError`

Example:

```text
TMDB error (/movie/12345): ConnectError('')
```

Usually caused by:

* Raspberry Pi networking issues
* DNS instability
* Too many parallel TLS connections
* Router/firewall interference
* ISP packet loss

Possible fixes:

* Lower concurrency
* Use stable DNS (1.1.1.1 / 8.8.8.8)
* Reduce simultaneous requests
* Check IPv6 configuration
* Verify router firewall settings

---

## API Endpoints Used

Search:

```text
/search/multi
/search/movie
/search/tv
```

Trending:

```text
/ trending/all/day
```

Metadata:

```text
/movie/{id}
/tv/{id}
```

Genres:

```text
/genre/movie/list
/genre/tv/list
```

Documentation:

[TMDB API Documentation](https://developer.themoviedb.org/docs/getting-started?utm_source=chatgpt.com)

---

## Future Improvements

* Redis cache
* Faster metadata loading
* Episode support
* Actor profiles
* Watch provider links
* Trailer support
* IMDb integration
* Persistent cache on disk

---

## License

MIT License

---

Powered by:

* [TMDB](https://www.themoviedb.org/?utm_source=chatgpt.com)
* [python-telegram-bot](https://python-telegram-bot.org/?utm_source=chatgpt.com)
* [httpx](https://www.python-httpx.org/?utm_source=chatgpt.com)

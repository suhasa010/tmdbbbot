import asyncio
import html
import logging
import os
import time

import httpx
from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.WARNING
)

log = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_KEY = os.getenv("TMDB_KEY")
TMDB_TOKEN = os.getenv("TMDB_TOKEN")

TMDB_API = "https://api.themoviedb.org/3"
IMAGE = "https://image.tmdb.org/t/p/w185"
POSTER = "https://image.tmdb.org/t/p/w500"
PAGE_SIZE = 10
QUERY_CACHE = {}
CACHE_TTL = 86400  # 1 day
PREFETCH_PAGES = 5  # how many TMDB pages to fetch initially

TMDB_HOST = "api.themoviedb.org"

client = None

# cache genres
movie_genres = {}
tv_genres = {}

sem = asyncio.Semaphore(3)

async def limited_build(media, item):
    async with sem:
        return await build_message(media, item)


async def tmdb_get(url, params=None, retries=5):

    for attempt in range(retries):
        try:
            log.info("TMDB request: %s attempt=%s", url, attempt + 1)

            r = await client.get(url, params=params)
            r.raise_for_status()

            return r.json()

        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            log.warning("TMDB error (%s): %r", url, type(e).__name__,
        e.__cause__)

            if attempt == retries - 1:
                log.error("TMDB failed after retries: %s", url)
                return {}

            await asyncio.sleep(2 ** attempt)

async def load_genres():
    global movie_genres, tv_genres

    movie_data = await tmdb_get(
        "/genre/movie/list",
    )

    tv_data = await tmdb_get(
        "/genre/tv/list",
    )

    movie_genres = {
        g["id"]: g["name"]
        for g in movie_data.get("genres", [])
    }

    tv_genres = {
        g["id"]: g["name"]
        for g in tv_data.get("genres", [])
    }


def year_from_date(date):
    if not date:
        return ""
    return date[:4]


def genre_string(ids, media):
    src = movie_genres if media == "movie" else tv_genres
    names = [src.get(i) for i in ids if src.get(i)]
    return ", ".join(names[:2])


def hashtag_genres(ids, media):
    src = movie_genres if media == "movie" else tv_genres
    tags = []

    for gid in ids[:3]:
        name = src.get(gid)

        if name:
            name = name.replace('&', '_')
            name = name.replace('-', '')
            name = name.replace(' ', '')

            tags.append(f"#{name}")

    return " ".join(tags)


async def build_message(media, item):
    id_ = item["id"]

    if media == "movie":
        url = f"/movie/{id_}"
    else:
        url = f"/tv/{id_}"

    data = await tmdb_get(
        url,
        {
            "append_to_response": "credits",
        },
    )

    if not data:
        raise RuntimeError(f"Empty TMDB response for {url}")

    poster_path = data.get("poster_path")
    poster_url = f"{POSTER}{poster_path}" if poster_path else ""

    title = data.get("title") or data.get("name")
    overview = data.get("overview", "No synopsis available.")


    date = data.get("release_date") if media == "movie" else data.get("first_air_date")
    year = f"({year_from_date(date)})" if date else ""
    type = media.title() if media == "movie" else media.upper()
    rating = data.get("vote_average", 0)
    genres = hashtag_genres(
        [g.get("id") for g in data.get("genres", []) if g.get("id")],
        media
    )

    lang = data.get("original_language", "N/A").upper()

    country = ""
    if data.get("origin_country"):
        country = ", ".join(data["origin_country"])
    elif data.get("production_countries"):
        country = ", ".join(c.get("name", "") for c in data["production_countries"])

    cast = data.get("credits", {}).get("cast", [])[:5]

    cast_str = []
    for c in cast:
        name = html.escape(c.get("name", "Unknown"))
        pid = c["id"]
        cast_str.append(
            f'<a href="https://www.themoviedb.org/person/{pid}">{name}</a>'
        )

    cast_line = ", ".join(cast_str)

    tmdb_link = f"https://www.themoviedb.org/{media}/{id_}"

    msg = f"""
<a href="{poster_url}">&#8203;</a>
<b><a href="{tmdb_link}">{html.escape(title)}</a> {year}</b> • {type}

<b>User Score ⭐️:</b> {rating} / 10

<b>Release Date:</b> {date or 'Unknown'}
<b>Genres:</b> {genres}
<b>Language:</b> {lang}
<b>Country of Origin:</b> {country}

<b>Overview:</b>
{html.escape(overview)}

<b>Cast:</b> {cast_line}...

<a href="{tmdb_link}">Read More ...</a>
"""

    return msg.strip()

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip().lower()
    log.info(
        "Inline query from %s: '%s'",
        update.inline_query.from_user.id,
        query
    )

    start_time = time.time()

    offset = int(update.inline_query.offset or 0)
    page = offset // PAGE_SIZE + 1

    cache_key = ("__TRENDING__", page) if not query else (query, page)
    cached = QUERY_CACHE.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        filtered = cached["results"]
        total_results = cached["total"]
        print("Fetching from cache", len(filtered), total_results)
    else:

        if not query:
            resp = await tmdb_get(
                "/trending/all/day",
                {"page": page}
            )
            query = ""

        else:
            resp = await tmdb_get(
                "/search/multi",
                {
                    "query": query,
                    "page": page,
                },
            )

            # fallback → movie search
            if not resp or not resp.get("results"):
                log.warning("multi search failed → trying movie search")

                resp = await tmdb_get(
                    "/search/movie",
                    {
                        "query": query,
                        "page": page,
                    },
                )

                if resp and resp.get("results"):
                    for r in resp["results"]:
                        r["media_type"] = "movie"

            # fallback → tv search
            if not resp or not resp.get("results"):
                log.warning("movie search failed → trying tv search")

                resp = await tmdb_get(
                    "/search/tv",
                    {
                        "query": query,
                        "page": page,
                    },
                )

                if resp and resp.get("results"):
                    for r in resp["results"]:
                        r["media_type"] = "tv"

            # final fallback → trending
            if not resp or not resp.get("results"):
                log.warning("all searches failed → falling back to trending")

                resp = await tmdb_get(
                    "/trending/all/day",
                    {"page": page}
                )

        data = resp.get("results", [])

        filtered = []

        for item in data:

            media = item.get("media_type")

            if media in ("movie", "tv") and item.get("id"):
                filtered.append(item)
                continue

            # handle person result
            if media == "person":

                known = item.get("known_for") or []

                for k in known:

                    if k.get("media_type") not in ("movie", "tv"):
                        continue

                    entry = k.copy()

                    entry["_person"] = item.get("name")
                    entry["_person_id"] = item.get("id")

                    filtered.append(entry)

        total_results = resp.get("total_results", len(filtered))

        QUERY_CACHE[cache_key] = {
            "ts": time.time(),
            "results": filtered,
            "total": total_results
        }

    items = filtered[:PAGE_SIZE]

    messages = await asyncio.gather(
        *(limited_build(item["media_type"], item) for item in items),
        return_exceptions=True
    )

    results = []
    for item, message in zip(items, messages):

        if isinstance(message, Exception):
            log.warning("Failed to build message for id=%r", item["id"])
            continue

        media = item["media_type"]
        title = item.get("title") or item.get("name")
        if "_person" in item:
            title = f"{item['_person']} • {title}"

        if media == "movie":
            date = item.get("release_date")
        else:
            date = item.get("first_air_date")

        year = year_from_date(date)
        type = media.upper() if media == "tv" else media.title()
        genres = genre_string(item.get("genre_ids", []), media)
        desc = f"{genres} • {year} • {type}" if genres else f"{year} • {type}"

        poster = item.get("poster_path")
        thumb = IMAGE + poster if poster else None

        results.append(
            InlineQueryResultArticle(
                id=f"{media}-{item['id']}",
                title=f"{title} ({year})",
                description=desc,
                thumbnail_url=thumb,
                input_message_content=InputTextMessageContent(
                    message,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                ),
            )
        )

    if not results:
        results.append(
            InlineQueryResultArticle(
                id="no-results",
                title="No results found",
                description="Try another search",
                input_message_content=InputTextMessageContent(
                    "No results available right now."
                )
            )
        )

    shown = (page - 1) * PAGE_SIZE + len(results)

    next_offset = offset + PAGE_SIZE
    if shown >= total_results:
        next_offset = ""
    else:
        next_offset = str(next_offset)

    await update.inline_query.answer(
        results,
        cache_time=600,
        is_personal=False,
        next_offset=next_offset,
        button=InlineQueryResultsButton(
            text=f"🔎 Showing {shown} of {total_results} results for \"{query}\"",
            start_parameter="inline"
        ),
    )

    elapsed = time.time() - start_time
    log.info("Inline query handled in %.2f sec", elapsed)
    asyncio.create_task(
       tmdb_get("/search/multi", {"query": query, "page": page + 1})
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("Start command from user %s", update.effective_user.id)
    text = f"""
🎬 <b>TMDB Inline Movie Bot</b>

Search movies and TV shows directly from any chat.

<b>How to use:</b>

1️⃣ Type:
<code>@{context.bot.username} breaking bad</code>

2️⃣ Choose a result from the list.

3️⃣ The bot will send full details including:
• Rating ⭐
• Release date
• Genres
• Overview
• Cast
• Poster

<b>Examples:</b>
<code>@{context.bot.username} dune</code>
<code>@{context.bot.username} game of thrones</code>

If you type only <code>@{context.bot.username}</code>, you will see today's trending movies and TV shows.
""".strip()

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "🔎 Search Movies and TV",
            switch_inline_query_current_chat=""
        )]]
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def error_handler(update, context):
    log.error("Telegram error: %s", context.error)

async def init_tmdb():
        global client
        client = httpx.AsyncClient(
            base_url="https://api.themoviedb.org/3",
            headers={
                "Authorization": f"Bearer {TMDB_TOKEN}",
                "accept": "application/json"
            },
            http2=False,
            timeout=httpx.Timeout(
                connect=4.0,
                read=10.0,
                write=10.0,
                pool=4.0
            ),
            limits=httpx.Limits(
    	    max_connections=10,
    	    max_keepalive_connections=10,
    	    keepalive_expiry=60
	    )
        )

        await load_genres()

def main():

    log.info("Starting TMDB inline bot")

    app = Application.builder().token(BOT_TOKEN).build()

    async def post_init(app):
        await init_tmdb()

    app.post_init = post_init

    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CommandHandler("start", start))
    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()



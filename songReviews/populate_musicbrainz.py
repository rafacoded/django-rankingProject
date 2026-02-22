import time
import requests
from pymongo import MongoClient
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MB_BASE = "https://musicbrainz.org/ws/2"
CAA_BASE = "https://coverartarchive.org"

HEADERS = {
    # Pon un user-agent “realista” (MusicBrainz lo pide)
    "User-Agent": "songReviews/1.0 (contact: unamamadote50@gmail.com)"
}

session = requests.Session()
retries = Retry(
    total=8,
    backoff_factor=1.2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
session.mount("https://", HTTPAdapter(max_retries=retries))

def mb_get(url, params=None):
    for attempt in range(1, 6):
        try:
            r = session.get(url, params=params, headers=HEADERS, timeout=30)
            # rate limit friendly (MusicBrainz recomienda ~1 req/seg)
            time.sleep(1.1)
            r.raise_for_status()
            return r.json()

        except requests.exceptions.RequestException as e:
            # Espera creciente y reintenta
            wait = min(10, 2 ** attempt)
            print(f"[WARN] Request failed ({attempt}/5): {e}. Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError("MusicBrainz request failed after retries.")


def caa_front_image_url(release_mbid: str) -> str | None:
    """Devuelve la URL de la portada frontal si existe."""
    try:
        r = requests.get(f"{CAA_BASE}/release/{release_mbid}", headers=HEADERS, timeout=20)
        time.sleep(0.5)
        if r.status_code != 200:
            return None
        data = r.json()
        images = data.get("images", [])
        # Busca front primero
        for img in images:
            if img.get("front") and "image" in img:
                return img["image"]
        # Si no hay front, cualquier image
        if images and "image" in images[0]:
            return images[0]["image"]
        return None
    except Exception:
        return None

def find_artist_mbid(artist_name: str) -> str | None:
    data = mb_get(f"{MB_BASE}/artist", params={
        "query": f'artist:"{artist_name}"',
        "fmt": "json",
        "limit": 1
    })
    artists = data.get("artists", [])
    if not artists:
        return None
    return artists[0]["id"]

def get_release_groups(artist_mbid: str, group_types=("album", "single", "ep"), limit=10):
    # Trae release-groups del artista
    data = mb_get(f"{MB_BASE}/release-group", params={
        "artist": artist_mbid,
        "fmt": "json",
        "limit": limit,
        "type": "|".join(group_types),
    })
    return data.get("release-groups", [])

def pick_release_with_cover(release_group_mbid: str) -> dict | None:
    data = mb_get(f"{MB_BASE}/release", params={
        "release-group": release_group_mbid,
        "fmt": "json",
        "limit": 10,   # prueba varios releases
    })
    releases = data.get("releases", [])
    if not releases:
        return None

    # 1) intenta encontrar uno con portada
    for rel in releases:
        if caa_front_image_url(rel["id"]):
            return rel

    # 2) si ninguno tiene, devuelve el primero (al menos hay datos)
    return releases[0]

def get_tracks_from_release(release_mbid: str) -> list[dict]:
    # Incluimos recordings para obtener duración (length)
    data = mb_get(f"{MB_BASE}/release/{release_mbid}", params={
        "inc": "recordings+artist-credits",
        "fmt": "json"
    })

    tracks_out = []
    media = data.get("media", [])
    for m in media:
        for t in m.get("tracks", []):
            title = t.get("title")
            length_ms = t.get("length")  # puede ser None
            # artista: usa credit del release si no hay en track
            ac = t.get("artist-credit") or data.get("artist-credit") or []
            artist = ac[0].get("name") if ac else None
            tracks_out.append({
                "title": title,
                "length_ms": length_ms,
                "artist": artist
            })
    return tracks_out

def iso_date_loose(d: str | None) -> str | None:
    return d if d else None

def main():
    # --- CONFIG ---
    # cambiar ARTISTS cada vez que se quiera importar
    ARTISTS = [ "Amy Winehouse", "Ralphie Choo", "ROSALÍA", "PinkPantheress", "Troye Sivan", "rusowsky", "Sabrina Carpenter"]
    MAX_RELEASE_GROUPS_PER_ARTIST = 5

    # Mongo
    client = MongoClient("mongodb://localhost:27017")
    db = client["songreviews"]
    col = db["songs"]

    # Traer dinámicamente el código disponible
    last = col.find_one(
        {"code": {"$exists": True}},
        sort=[("code", -1)],
        projection={"code": 1}
    )

    code = (last["code"] if last else 0) + 1

    for artist_name in ARTISTS:
        artist_mbid = find_artist_mbid(artist_name)
        if not artist_mbid:
            print(f"[WARN] No artist found: {artist_name}")
            continue

        rgs = get_release_groups(artist_mbid, limit=MAX_RELEASE_GROUPS_PER_ARTIST)
        print(f"[INFO] {artist_name}: {len(rgs)} release-groups")

        for rg in rgs:
            rg_title = rg.get("title")
            rg_first_release = iso_date_loose(rg.get("first-release-date"))
            rg_type = rg.get("primary-type")

            release = pick_release_with_cover(rg["id"])
            if not release:
                print(f"[WARN] No release for group: {rg_title}")
                continue

            release_mbid = release["id"]
            cover_url = caa_front_image_url(release_mbid)

            tracks = get_tracks_from_release(release_mbid)
            if not tracks:
                # Si no hay tracklist, al menos guardamos un “item” (opcional)
                print(f"[WARN] No tracks in release: {rg_title}")
                continue

            # Inserta tracks como canciones
            docs = []
            for tr in tracks:
                title = tr["title"]
                if not title:
                    continue

                duration_sec = None
                if tr["length_ms"] is not None:
                    duration_sec = int(tr["length_ms"] / 1000)

                doc = {
                    "code": code,
                    "name": title,
                    "artist": tr["artist"] or artist_name,
                    "duration": duration_sec if duration_sec is not None else 0,
                    "artwork": cover_url or "",  # si no hay, vacío
                    "releaseDate": rg_first_release or "",
                    "categories": [],
                    # extras útiles (no estorban)
                    "source": "musicbrainz",
                    "release_group": rg_title,
                    "release_group_type": rg_type,
                    "release_mbid": release_mbid,
                }
                docs.append(doc)
                code += 1

            if docs:
                # evita duplicados por (name+artist+release_mbid) de forma sencilla
                # (mejor sería un índice único, pero para pruebas vale)
                inserted = 0
                for d in docs:
                    exists = col.find_one({
                        "name": d["name"],
                        "artist": d["artist"],
                        "release_mbid": d["release_mbid"]
                    }, {"_id": 1})
                    if not exists:
                        col.insert_one(d)
                        inserted += 1

                print(f"[OK] Inserted {inserted} tracks from: {artist_name} — {rg_title}")

    print("[DONE] Finished populating.")

if __name__ == "__main__":
    main()

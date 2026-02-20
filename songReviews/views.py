import csv
import json

from django.contrib.auth import login, authenticate, logout
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect

from songReviews.forms import LoginForm, RegisterForm
from songReviews.models import *

# USER FUNCTIONS
def go_door(request):
    return render(request, 'door.html')

def go_home(request):
    return render(request, 'home.html')

def show_songs(request):
    q = (request.GET.get("q") or "").strip()

    songs = Song.objects.all()

    if q:
        songs = songs.filter(
            Q(name__icontains=q) | Q(artist__icontains=q)
        )

    return render(request, "songs.html", {"songs": songs, "q": q})


def view_song(request, songCode):
    song = mongo(Song).get(code=int(songCode))

    client = MongoClient("mongodb://localhost:27017")
    db = client["songreviews"]
    reviews_col = db["reviews"]

    reviews = list(
        reviews_col.find(
            {"songCode": int(songCode)},
            {"_id": 0}
        ).sort("reviewDate", -1)
    )

    avg_rating = None
    if reviews:
        avg_rating = round(sum(r["rating"] for r in reviews) / len(reviews), 2)

    # UPDATE (if existing)
    my_review = None
    has_my_review = False
    if request.user.is_authenticated:
        my_review = reviews_col.find_one(
            {"songCode": int(songCode), "user": request.user.username},
            {"_id": 0}
        )
        has_my_review = my_review is not None

    return render(request, "song_view.html", {
        "song": song,
        "reviews": reviews,
        "avg_rating": avg_rating,
        "my_review": my_review,
        "has_my_review": has_my_review,
    })

def add_review(request, songCode):
    if request.method != "POST":
        return redirect("view_song", songCode=songCode)

    if not request.user.is_authenticated:
        return redirect("do_login")

    rating = request.POST.get("rating")
    comments = (request.POST.get("comments") or "").strip()

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return redirect("view_song", songCode=songCode)

    if rating < 1 or rating > 5 or not comments:
        return redirect("view_song", songCode=songCode)

    username = (
        request.user.username
        if request.user.is_authenticated
        else "Anonymous User"
    )

    client = MongoClient("mongodb://localhost:27017")
    db = client["songreviews"]
    reviews_col = db["reviews"]

    # Upsert lowkey
    reviews_col.update_one(
        {"user": username, "songCode": int(songCode)},
        {"$set": {
            "reviewDate": timezone.now(),
            "rating": rating,
            "comments": comments,
        }},
        upsert=True
    )

    return redirect("view_song", songCode=songCode)

def go_ranking(request, category_code):
    category_code = int(category_code)

    category = mongo(Category).get(code=category_code)
    songs = mongo(Song).filter(categories__contains=[category_code])

    saved_tiers = None
    has_saved = False

    if request.user.is_authenticated:
        username = request.user.username
        existing = mongo(Ranking).filter(
            user=username,
            categoryCode=category_code
        ).order_by("-rankingDate").first()

        if existing:
            has_saved = True
            saved_tiers = {"S": [], "A": [], "B": [], "C": [], "D": []}
            for item in (existing.rankList or []):
                tier = item.get("tier")
                song = item.get("song")
                if tier in saved_tiers and song is not None:
                    saved_tiers[tier].append(int(song))

    return render(request, "ranking_category.html", {
        "category": category,
        "items": songs,
        "category_code": category_code,
        "category_size": songs.count(),
        "tiers": ["S", "A", "B", "C", "D"],
        "saved_tiers": json.dumps(saved_tiers),
        "has_saved": has_saved,
    })

def save_tierlist(request):
    if request.method != "POST":
        return redirect("go_home")

    if not request.user.is_authenticated:
        return redirect("do_login")

    category_code = int(request.POST.get("category_code"))
    tier_data = json.loads(request.POST.get("tier_data"))

    username = request.user.username

    tier_score = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}

    rank_list = []
    for tier, songs in tier_data.items():
        for song_code in songs:
            rank_list.append({
                "song": int(song_code),
                "tier": tier,
                "score": tier_score.get(tier, 0),
            })

    existing = mongo(Ranking).filter(
        user=username,
        categoryCode=category_code
    ).first()

    if existing:
        # UPDATE
        mongo(Ranking).filter(id=existing.id).update(
            rankingDate=timezone.now(),
            rankList=rank_list
        )
    else:
        # CREATE
        ranking = Ranking()
        ranking.user = username
        ranking.rankingDate = timezone.now()
        ranking.categoryCode = category_code
        ranking.rankList = rank_list
        ranking.save(using="mongodb")

    return redirect("go_ranking", category_code=category_code)


# -- ADMIN FUNCTIONS --
def go_categories(request):

    q = (request.GET.get("q") or "").strip()

    categories = mongo(Category).all().order_by("code")
    songs = mongo(Song).all().order_by("code")

    if q:
        songs = songs.filter(Q(name__icontains=q) | Q(artist__icontains=q))

    if request.method == "POST":
        category = Category()
        category.name = request.POST.get("name")
        category.description = request.POST.get("description")
        category.logo = request.POST.get("logo")

        last = mongo(Category).order_by("code").last()
        category.code = (last.code if last else 0) + 1
        category.save(using="mongodb")

        return redirect("go_categories")

    return render(request, "categories.html", {
        "categories": categories,
        "songs": songs,
        "q": q,
    })

def add_songs_category(request):
    selected = json.loads(request.POST.get("songs", "[]"))
    category_codes = json.loads(request.POST.get("category_codes", "[]"))

    selected_codes = [int(x) for x in selected]
    category_codes = [int(x) for x in category_codes]

    if not selected_codes or not category_codes:
        return redirect("go_categories")

    client = MongoClient("mongodb://localhost:27017")
    col = client["songreviews"]["songs"]

    col.update_many(
        {"code": {"$in": selected_codes}},
        {"$addToSet": {"categories": {"$each": category_codes}}}
    )

    return redirect("go_categories")

def show_categories(request):
    categories = mongo(Category).all().order_by('code')
    return render(request, "ranking.html", {"categories": categories})

def update_category(request):
    if request.method != "POST":
        return redirect("go_categories")

    code = int(request.POST.get("code"))
    name = (request.POST.get("name") or "").strip()
    logo = (request.POST.get("logo") or "").strip()
    description = (request.POST.get("description") or "").strip()

    if not name or not logo or not description:
        return redirect("go_categories")

    mongo(Category).filter(code=code).update(
        name=name,
        logo=logo,
        description=description
    )

    return redirect("go_categories")

def category_songs(request, code):
    code = int(code)

    songs = mongo(Song).filter(categories__contains=[code]).order_by("code")

    data = []
    for s in songs:
        data.append({
            "code": int(s.code),
            "name": s.name,
            "artist": s.artist,
            "artwork": s.artwork,
        })

    return JsonResponse({"songs": data})


def remove_songs_category(request, code):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    code = int(code)
    song_codes = request.POST.getlist("song_codes[]")

    try:
        song_codes = [int(x) for x in song_codes]
    except ValueError:
        return JsonResponse({"ok": False, "error": "Bad song codes"}, status=400)

    if not song_codes:
        return JsonResponse({"ok": False, "error": "No songs selected"}, status=400)

    client = MongoClient("mongodb://localhost:27017")
    col = client["songreviews"]["songs"]

    res = col.update_many(
        {"code": {"$in": song_codes}},
        {"$pull": {"categories": code}}
    )

    return JsonResponse({"ok": True, "modified": res.modified_count})

def delete_category(request, code):
    code = int(code)
    mongo(Category).filter(code=code).delete()

    client = MongoClient("mongodb://localhost:27017")
    col = client["songreviews"]["songs"]
    col.update_many({"categories": code}, {"$pull": {"categories": code}})

    return redirect("go_categories")


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from pymongo import MongoClient

@login_required
def stats(request):
    client = MongoClient("mongodb://localhost:27017")
    db = client["songreviews"]

    rankings_col = db["ranking"]

    # Resumen global
    total_rankings = rankings_col.count_documents({})

    total_ratings_agg = list(rankings_col.aggregate([
        {"$unwind": "$rankList"},
        {"$group": {"_id": None, "total": {"$sum": 1}}}
    ]))
    total_ratings = int(total_ratings_agg[0]["total"]) if total_ratings_agg else 0

    # Top canciones por media (más valoradas)
    top_avg_pipeline = [
        {"$unwind": "$rankList"},
        {"$group": {
            "_id": "$rankList.song",
            "avgScore": {"$avg": "$rankList.score"},
            "votes": {"$sum": 1},
        }},
        {"$sort": {"avgScore": -1, "votes": -1}},
        {"$limit": 20},
        {"$lookup": {
            "from": "songs",
            "localField": "_id",
            "foreignField": "code",
            "as": "song"
        }},
        {"$unwind": {"path": "$song", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "code": "$_id",
            "avg": {"$round": ["$avgScore", 2]},
            "votes": 1,
            "name": {"$ifNull": ["$song.name", {"$concat": ["Song #", {"$toString": "$_id"}]}]},
            "artist": {"$ifNull": ["$song.artist", ""]},
            "artwork": {"$ifNull": ["$song.artwork", ""]},
        }},
    ]
    top_avg = list(rankings_col.aggregate(top_avg_pipeline))

    # Top "mejores puestos" (por % de tier S)
    top_s_pipeline = [
        {"$unwind": "$rankList"},
        {"$group": {
            "_id": "$rankList.song",
            "votes": {"$sum": 1},
            "sCount": {"$sum": {"$cond": [{"$eq": ["$rankList.score", 5]}, 1, 0]}},
            "topCount": {"$sum": {"$cond": [{"$gte": ["$rankList.score", 4]}, 1, 0]}},
        }},
        {"$addFields": {
            "sRate": {"$cond": [{"$gt": ["$votes", 0]}, {"$divide": ["$sCount", "$votes"]}, 0]},
            "topRate": {"$cond": [{"$gt": ["$votes", 0]}, {"$divide": ["$topCount", "$votes"]}, 0]},
        }},

        {"$match": {"votes": {"$gte": 2}}},
        {"$sort": {"sRate": -1, "votes": -1}},
        {"$limit": 20},
        {"$lookup": {
            "from": "songs",
            "localField": "_id",
            "foreignField": "code",
            "as": "song"
        }},
        {"$unwind": {"path": "$song", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "code": "$_id",
            "votes": 1,
            "sCount": 1,
            "topCount": 1,
            "sRate": {"$round": [{"$multiply": ["$sRate", 100]}, 1]},
            "topRate": {"$round": [{"$multiply": ["$topRate", 100]}, 1]},
            "name": {"$ifNull": ["$song.name", {"$concat": ["Song #", {"$toString": "$_id"}]}]},
            "artist": {"$ifNull": ["$song.artist", ""]},
            "artwork": {"$ifNull": ["$song.artwork", ""]},
        }},
    ]
    top_s = list(rankings_col.aggregate(top_s_pipeline))

    # Promedio por categoría (score medio global por categoría)
    cat_pipeline = [
        {"$unwind": "$rankList"},
        {"$group": {
            "_id": "$categoryCode",
            "avgScore": {"$avg": "$rankList.score"},
            "ratings": {"$sum": 1},
            "rankings": {"$addToSet": "$_id"},
        }},
        {"$addFields": {"rankingCount": {"$size": "$rankings"}}},
        {"$sort": {"avgScore": -1, "ratings": -1}},
        {"$limit": 50},
        {"$lookup": {
            "from": "categories",
            "localField": "_id",
            "foreignField": "code",
            "as": "cat"
        }},
        {"$unwind": {"path": "$cat", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "code": "$_id",
            "avg": {"$round": ["$avgScore", 2]},
            "ratings": 1,
            "rankingCount": 1,
            "name": {"$ifNull": ["$cat.name", {"$concat": ["Category #", {"$toString": "$_id"}]}]},
            "logo": {"$ifNull": ["$cat.logo", ""]},
        }},
    ]
    categories = list(rankings_col.aggregate(cat_pipeline))

    overview = {
        "total_rankings": total_rankings,
        "total_ratings": total_ratings,
    }

    return render(request, "stats.html", {
        "overview": overview,
        "top_avg": top_avg,
        "top_s": top_s,
        "categories": categories,
    })


def data_load(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get('csvFile')

        if not uploaded_file:
            return render(request, 'data_load.html', {
                'error': 'No se seleccionó ningún archivo.'
            })

        decoded_file = uploaded_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        for row in reader:
            try:
                categories = [
                    int(c.strip())
                    for c in row["categories"].split(",")
                    if c.strip().isdigit()
                ]

                song = Song(
                    code=int(row['code']),
                    name=row['name'],
                    artist=row['artist'],
                    duration=int(row['duration']),
                    artwork=row["artwork"],
                    releaseDate = row['releaseDate'],
                    categories=categories,
                )
                song.save()

            except Exception as e:
                print("Error en fila: ", row, e)

        return render(request, 'data_load.html', {
            'success': "Canciones cargadas correctamente."
        })
    return render(request, 'data_load.html')

def admin_panel(request):
    if getattr(request.user, "role", None) != "admin":
        return HttpResponseForbidden("Not allowed")

    return render(request, 'admin.html')

# -- ACCESS FUNCTIONS --
def do_login(request):

    if request.method == 'POST':

        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect('go_home')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})

def do_register(request):

    if request.method == 'POST':

        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            return redirect('do_login')

        return render(request, 'register.html', {'form': form})

    form = RegisterForm()
    return render(request, 'register.html', {'form': form})

def do_logout(request):
    logout(request)
    return render(request, 'door.html')

# UTILS
def mongo(model):
    return model.objects.using("mongodb")
from django.contrib import admin
from django.urls import path, include
from songReviews.views import *

urlpatterns = [
    path('', go_door, name='go_door'),
    path('home/', go_home, name='go_home'),
    path('songs/', show_songs, name='show_songs'),
    path('songs/<int:songCode>/', view_song, name='view_song'),
    path('songs/<int:songCode>/review', add_review, name='add_review'),
    path('ranking/', show_categories, name='show_categories'),
    path('ranking/<int:category_code>/', go_ranking, name='go_ranking'),
    path('ranking/save/', save_tierlist, name='save_tierlist'),
    path('stats/global/', stats, name="stats"),

    # ADMIN PANEL CONTROL
    
    path('admin-panel/data_load', data_load, name='data_load'),
    path('admin-panel/categories/', go_categories, name='go_categories'),
    path("admin-panel/categories/<int:code>/songs/", category_songs, name="category_songs"),
    path("admin-panel/categories/<int:code>/songs/remove/", remove_songs_category, name="remove_songs_from_category"),
    path("admin-panel/categories/add-songs", add_songs_category, name="add_songs_category"),
    path("admin-panel/categories/update/", update_category, name="update_category"),
    path('admin-panel/categories/delete/<int:code>/', delete_category, name='delete_category'),
    path('admin-panel', admin_panel, name='admin_panel'),
    path("admin-panel/users-panel/", users_panel, name="users_panel"),

    # ACCESS

    path('login/', do_login, name='do_login'),
    path('register/', do_register, name='do_register'),
    path('logout/', do_logout, name='do_logout'),
]

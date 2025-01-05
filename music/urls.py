from django.urls import path
from . import views

urlpatterns = [
    path('callback', views.callback, name='callback'),
    path('search/', views.search, name='search'),

    path('track/<str:track_name>/redirect/', views.track_redirection, name='track_redirection'),
    path('track/<str:track_id>/', views.track_detail, name='track_detail'),
    path('artist/<str:artist_name>/', views.artist_detail, name='artist_detail'),
    path('playlist/<str:playlist_id>/', views.playlist_detail, name='playlist_detail'),
    path('create-playlist/', views.create_playlist, name='create_playlist'),
    path('add-to-playlist/', views.add_to_playlist, name='add_to_playlist'),
]

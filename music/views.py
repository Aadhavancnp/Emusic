from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import cache_page

from users.models import UserActivity
from .models import Playlist
from .spotify import get_recommendations, get_spotify_client, \
    search_jiosaavn, get_track_details_jiosaavn, get_user_top_tracks, get_user_recently_played, get_playlist_details, \
    create_playlist_spotify


@login_required
def search(request):
    query = request.GET.get('q', '')
    tracks = []
    if query:
        tracks = search_jiosaavn(query)
    context = {
        'query': query,
        'tracks': tracks,
    }
    return render(request, 'music/search.html', context)


def callback(request):
    code = request.GET.get('code')
    sp = get_spotify_client(request)
    token_info = sp.auth_manager.get_access_token(code)
    request.session['token_info'] = token_info
    return redirect('dashboard')


@login_required
@cache_page(60 * 15)
def track_detail(request, track_id):
    track = get_track_details_jiosaavn(track_id)
    sp = get_spotify_client(request)
    top_tracks = get_user_top_tracks(sp)
    recently_played = get_user_recently_played(sp)
    recommendations = get_recommendations(track_id, top_tracks + recently_played, limit=5)
    artists = [{'name': artist.strip(), 'url': reverse('artist_detail', args=[artist.strip()])}
               for artist in track['artist'].split(',')]
    audio_features_cache_key = f"audio_features_{track_id}"
    cached_audio_features = cache.get(audio_features_cache_key)

    if cached_audio_features:
        track["audio_features"] = cached_audio_features
    else:
        track["audio_features"] = {}

    # Log user activity
    UserActivity.objects.create(
        user=request.user,
        activity_type='view_track',
        description=f"Viewed track: {track['name']} by {track['artist']}"
    )
    context = {
        'track': track,
        'recommendations': recommendations,
        'artists': artists
    }

    return render(request, 'music/track_detail.html', context)


def track_redirection(request, track_name):
    track = search_jiosaavn(track_name)[0]
    if track:
        return redirect('track_detail', track_id=track['id'])
    return redirect('search')


@login_required
def artist_detail(request, artist_name):
    sp = get_spotify_client(request)
    artist_id = sp.search(artist_name, type='artist')['artists']['items'][0]['id']
    artist = sp.artist(artist_id)
    top_tracks = sp.artist_top_tracks(artist_id)['tracks'][:5]
    albums = sp.artist_albums(artist_id, album_type='album', limit=5)['items']

    context = {
        'artist': artist,
        'top_tracks': top_tracks,
        'albums': albums,
    }
    return render(request, 'music/artist_detail.html', context)


@login_required
def playlist_detail(request, playlist_id):
    sp = get_spotify_client(request)
    playlist = get_playlist_details(sp, playlist_id)

    context = {
        'playlist': playlist
    }
    return render(request, 'music/playlist_detail.html', context)


@login_required
def create_playlist(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        sp = get_spotify_client(request)
        playlist = create_playlist_spotify(sp, name, description)

        # Create a local record of the playlist
        Playlist.objects.create(
            user=request.user,
            spotify_id=playlist['id'],
            name=playlist['name']
        )

        return redirect('playlist_detail', playlist_id=playlist['id'])
    return render(request, 'music/create_playlist.html')


@login_required
def add_to_playlist(request):
    if request.method == 'POST':
        track_id = request.POST.get('track_id')
        playlist_id = request.POST.get('playlist_id')
        sp = get_spotify_client(request)
        sp.playlist_add_items(playlist_id, [track_id])
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

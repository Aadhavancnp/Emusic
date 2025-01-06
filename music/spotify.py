import os
import re
from functools import lru_cache

import librosa
import numpy as np
import requests
import spotipy
from django.conf import settings
from django.core.cache import cache
from sklearn.metrics.pairwise import cosine_similarity
from spotipy.oauth2 import SpotifyOAuth


@lru_cache(maxsize=100)
def get_spotify_client(request):
    cache_handler = spotipy.cache_handler.DjangoSessionCacheHandler(request)
    auth_manager = SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope='user-library-read playlist-read-private playlist-modify-public playlist-modify-private user-top-read user-read-recently-played',
        cache_handler=cache_handler
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def search_tracks(sp, query, limit=10):
    cache_key = f"spotify_search_{query}_{limit}"
    cached_results = cache.get(cache_key)
    if cached_results:
        return cached_results
    results = sp.search(q=query, type='track', limit=limit)
    cache.set(cache_key, results['tracks']['items'], 60 * 15)
    return results['tracks']['items']


def get_user_playlists(sp):
    cache_key = f'user_playlists_{sp.current_user()["id"]}'
    cached_playlists = cache.get(cache_key)
    if cached_playlists:
        return cached_playlists

    playlists = sp.current_user_playlists()
    result = [
        {
            'name': playlist['name'],
            'id': playlist['id'],
            'tracks': get_playlist_tracks(sp, playlist['id'])
        }
        for playlist in playlists['items']
    ]
    cache.set(cache_key, result, 60 * 60)  # Cache for 1 hour
    return result


def get_playlist_tracks(sp, playlist_id):
    cache_key = f"playlist_tracks_{playlist_id}"
    cached_tracks = cache.get(cache_key)
    if cached_tracks:
        return cached_tracks

    results = sp.playlist_tracks(playlist_id)
    tracks = [
        {
            'name': track['track']['name'],
            'artist': track['track']['artists'][0]['name'],
            'album': track['track']['album']['name'],
            'duration': track['track']['duration_ms'],
            'id': track['track']['id']
        }
        for track in results['items']
    ]
    cache.set(cache_key, tracks, 60 * 20)  # Cache for 20 minutes
    return tracks


def get_user_top_tracks(sp):
    cache_key = f'user_top_tracks_{sp.current_user()["id"]}'
    cached_top_tracks = cache.get(cache_key)
    if cached_top_tracks:
        return cached_top_tracks
    results = sp.current_user_top_tracks(limit=50, time_range='medium_term')
    top_tracks = [
        {
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'album': track['album']['name'],
            'id': track['id']
        }
        for track in results['items']
    ]
    cache.set(cache_key, top_tracks, 3600)  # Cache for 1 hour
    return top_tracks


def get_user_recently_played(sp):
    cache_key = f'user_recently_played_{sp.current_user()["id"]}'
    cached_recently_played = cache.get(cache_key)
    if cached_recently_played:
        return cached_recently_played

    results = sp.current_user_recently_played(limit=50)
    recently_played = [
        {
            'name': track['track']['name'],
            'artist': track['track']['artists'][0]['name'],
            'album': track['track']['album']['name'],
            'id': track['track']['id'],
            'played_at': track['played_at']
        }
        for track in results['items']
    ]
    cache.set(cache_key, recently_played, 900)  # Cache for 15 minutes
    return recently_played


def get_artist_top_tracks(sp, artist_id):
    cache_key = f"spotify_artist_top_tracks_{artist_id}"
    cached_tracks = cache.get(cache_key)
    if cached_tracks:
        return cached_tracks
    results = sp.artist_top_tracks(artist_id)
    cache.set(cache_key, results['tracks'], 60 * 5)
    return results['tracks']


def search_jiosaavn(query, limit=10):
    cache_key = f'jiosaavn_search_{query}_{limit}'
    cached_results = cache.get(cache_key)
    if cached_results:
        return cached_results

    url = f"https://www.jiosaavn.com/api.php?__call=autocomplete.get&query={query}&_format=json&_marker=0&ctx=web6dot0&includeMetaTags=1"
    response = requests.get(url)
    data = response.json()

    tracks = []
    for song in data.get('songs', {}).get('data', [])[:limit]:
        song_details = get_track_details_jiosaavn(song['id'])
        tracks.append({
            'id': song['id'],
            'name': song['title'],
            'artist': song_details['artist'],
            'album': song_details['album'],
            'year': song_details['year'],
            'image_url': song_details['image_url'],
            'duration': song_details['duration'],
            'preview_url': song_details['preview_url'],
        })

    cache.set(cache_key, tracks, 3600)  # Cache for 1 hour
    return tracks


def get_track_details_jiosaavn(track_id):
    cache_key = f'jiosaavn_track_{track_id}'
    cached_track = cache.get(cache_key)
    if cached_track:
        return cached_track
    url = f"https://www.jiosaavn.com/api.php?__call=song.getDetails&pids={track_id}&_format=json&_marker=0&ctx=web6dot0"
    response = requests.get(url)
    data = response.json().get('songs', [])[0]

    track = {
        'id': data['id'],
        'name': data['song'],
        'artist': data['primary_artists'],
        'album': data['album'],
        'year': data['year'],
        'image_url': re.sub(r'\d+x\d+', '500x500', data['image']),
        'duration': int(data['duration']) * 1000,
        'preview_url': data['vlink'] if data.get('vlink') else data.get('media_preview_url', '')
    }

    cache.set(cache_key, track, 3600)  # Cache for 1 hour
    return track


@lru_cache(maxsize=50)
def extract_audio_features(audio_file):
    y, sr = librosa.load(audio_file)

    # Extract features
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    chroma_stft = librosa.feature.chroma_stft(y=y, sr=sr)
    rmse = librosa.feature.rms(y=y)
    spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)
    spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)
    mfcc = librosa.feature.mfcc(y=y, sr=sr)

    return {
        'tempo': float(tempo),
        'chroma_stft_mean': float(np.mean(chroma_stft)),
        'rmse_mean': float(np.mean(rmse)),
        'spectral_centroid_mean': float(np.mean(spec_cent)),
        'spectral_bandwidth_mean': float(np.mean(spec_bw)),
        'rolloff_mean': float(np.mean(rolloff)),
        'zero_crossing_rate_mean': float(np.mean(zcr)),
        'mfcc_mean': float(np.mean(mfcc)),
    }


def download_preview(preview_url, track_id):
    if track_id in os.listdir(os.path.join(settings.MEDIA_ROOT, 'previews')):
        return os.path.join(settings.MEDIA_ROOT, 'previews', f'{track_id}.mp3')
    response = requests.get(preview_url)
    if response.status_code == 200:
        file_path = os.path.join(settings.MEDIA_ROOT, 'previews', f'{track_id}.mp3')
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        return file_path
    return None


def get_recommendations(track_id, stored_tracks, limit=10):
    cache_key = f'recommendations_{track_id}_{limit}'
    cached_recommendations = cache.get(cache_key)
    if cached_recommendations:
        return cached_recommendations

    target_track = get_track_details_jiosaavn(track_id)
    preview_file = download_preview(target_track['preview_url'], track_id)

    if preview_file:
        target_features = extract_audio_features(preview_file)

        target_features_scalar = {k: float(v) for k, v in target_features.items()}

        similarities = []
        for stored_track in stored_tracks:
            search = f"{stored_track['name']} {stored_track['artist']}"
            results = search_jiosaavn(search)
            if not results:
                continue

            preview_path = download_preview(results[0]['preview_url'], stored_track['id'])
            if not preview_path:
                continue

            audio_cache_key = f"audio_features_{track_id}"
            cached_audio_features = cache.get(audio_cache_key)
            if cached_audio_features:
                stored_features = cached_audio_features
            else:
                stored_features = extract_audio_features(preview_path)
                cache.set(audio_cache_key, stored_features, 3600)  # Cache for 1 hour
            stored_features_scalar = {k: float(v) for k, v in stored_features.items()}

            target_vector = np.array(list(target_features_scalar.values()))
            stored_vector = np.array(list(stored_features_scalar.values()))

            similarity = cosine_similarity(
                target_vector.reshape(1, -1),
                stored_vector.reshape(1, -1)
            )[0][0]
            similarities.append((stored_track, similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)
        recommendations = [track for track, _ in similarities[:limit]]
        cache.set(cache_key, recommendations, 3600)  # Cache for 1 hour
        return recommendations

    return []


def create_playlist_spotify(sp, name, description=""):
    user_id = sp.current_user()['id']
    playlist = sp.user_playlist_create(user_id, name, public=False, description=description)
    return playlist


def get_playlist_details(sp, playlist_id):
    playlist = sp.playlist(playlist_id)
    tracks = playlist['tracks']['items']
    return {
        'id': playlist['id'],
        'name': playlist['name'],
        'description': playlist['description'],
        'tracks': [
            {
                'id': track['track']['id'],
                'name': track['track']['name'],
                'artist': track['track']['artists'][0]['name'],
                'album': track['track']['album']['name'],
                'duration': track['track']['duration_ms'],
                'preview_url': track['track']['preview_url']
            }
            for track in tracks
        ]
    }


def get_artist_details(sp, artist_id):
    artist = sp.artist(artist_id)
    top_tracks = sp.artist_top_tracks(artist_id)['tracks']
    albums = sp.artist_albums(artist_id, album_type='album', limit=5)['items']
    related_artists = sp.artist_related_artists(artist_id)['artists'][:5]

    return {
        'id': artist['id'],
        'name': artist['name'],
        'genres': artist['genres'],
        'popularity': artist['popularity'],
        'image_url': artist['images'][0]['url'] if artist['images'] else None,
        'top_tracks': [
            {
                'id': track['id'],
                'name': track['name'],
                'album': track['album']['name'],
                'preview_url': track['preview_url']
            }
            for track in top_tracks[:5]
        ],
        'albums': [
            {
                'id': album['id'],
                'name': album['name'],
                'release_date': album['release_date'],
                'image_url': album['images'][0]['url'] if album['images'] else None
            }
            for album in albums
        ],
        'related_artists': [
            {
                'id': related['id'],
                'name': related['name'],
                'image_url': related['images'][0]['url'] if related['images'] else None
            }
            for related in related_artists
        ]
    }


def calculate_listening_time(recently_played):
    return 100
    # return sum(track['duration'] for track in recently_played) / (1000 * 60 * 60)  # Convert to hours


def get_favorite_genre(sp, top_tracks):
    cache_key = f"favorite_genre_{sp.current_user()['id']}"
    cached_genre = cache.get(cache_key)
    if cached_genre:
        return cached_genre
    if not top_tracks:
        return None
    artists = [track['artist'] for track in top_tracks]
    artist_genres = [sp.artist(sp.search(artist, type='artist')['artists']['items'][0]['id'])['genres'] for artist in
                     artists]
    all_genres = [genre for genres in artist_genres for genre in genres]
    cache.set(cache_key, max(set(all_genres), key=all_genres.count), 3600)  # Cache for 1 hour
    return max(set(all_genres), key=all_genres.count) if all_genres else None

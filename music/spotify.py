import os
import re
from collections import Counter
from datetime import datetime, timedelta
from functools import lru_cache

import librosa
import numpy as np
import requests
import spotipy
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from sklearn.metrics.pairwise import cosine_similarity
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

from music.models import Track, Artist, Genre, Playlist
from music.utils import translate_text


@lru_cache(maxsize=100)
def get_spotify_client(request):
    cache_handler = spotipy.cache_handler.DjangoSessionCacheHandler(request)
    auth_manager = SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=settings.SPOTIFY_SCOPE,
        cache_handler=cache_handler
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def search_tracks(sp, query, limit=10):
    cache_key = f"spotify_search_{query}_{limit}"
    cached_results = cache.get(cache_key)
    if cached_results:
        return cached_results
    results = sp.search(q=query, type='track', limit=limit)
    tracks = []

    for spotify_track in results['tracks']['items']:
        track = get_or_create_track(spotify_track, sp)
        tracks.append(track)
    cache.set(cache_key, tracks, 900)  # Cache for 15 minutes
    return tracks


def get_or_create_track(track_data, sp: Spotify):
    spotify_id = track_data['id']
    if not spotify_id:
        return None

    track = Track.objects.filter(spotify_id=spotify_id).first()
    if track:
        return track

    artists = []
    for artist_data in track_data.get('artists', []):
        artist, _ = Artist.objects.get_or_create(
            spotify_id=artist_data['id'],
            defaults={'name': artist_data['name']}
        )
        artists.append(artist)

    artist_ids = [artist.spotify_id for artist in artists if artist.spotify_id]
    genres = set()
    if artist_ids:
        spotify_artists = sp.artists(artist_ids).get('artists', [])
        for spotify_artist, artist in zip(spotify_artists, artists):
            artist_genres = [
                Genre.objects.get_or_create(name=genre_name)[0]
                for genre_name in spotify_artist.get('genres', [])
            ]
            artist.genres.set(artist_genres)
            artist.save()
            genres.update(spotify_artist.get('genres', []))

    genre, _ = Genre.objects.get_or_create(name=next(iter(genres), 'Unknown'))

    release_date = None
    release_precision = track_data['album'].get('release_date_precision')
    release_date_str = track_data['album'].get('release_date')

    if release_date_str and release_precision:
        try:
            if release_precision == 'day':
                release_date = datetime.strptime(release_date_str, '%Y-%m-%d')
            elif release_precision == 'year':
                release_date = datetime.strptime(release_date_str, '%Y')
        except ValueError:
            release_date = None

    track = Track.objects.create(
        title=track_data.get('name'),
        genre=genre,
        spotify_id=spotify_id,
        album=track_data['album'].get('name'),
        duration=timedelta(milliseconds=track_data.get('duration_ms', 0)),
        preview_url=track_data.get('preview_url'),
        image_url=track_data['album'].get('images')[0].get('url') if track_data['album'].get('images') else None,
        popularity=track_data.get('popularity', 0),
        release_date=release_date,
        audio_features={}
    )
    track.artists.set(artists)
    track.save()

    return track


def update_song_audio_features(song, audio_features):
    song.audio_features.update({
        "tempo": audio_features['tempo'],
        "chroma_stft_mean": audio_features['chroma_stft_mean'],
        "rmse_mean": audio_features['rmse_mean'],
        "spectral_centroid_mean": audio_features['spectral_centroid_mean'],
        "spectral_bandwidth_mean": audio_features['spectral_bandwidth_mean'],
        "rolloff_mean": audio_features['rolloff_mean'],
        "zero_crossing_rate_mean": audio_features['zero_crossing_rate_mean'],
        "mfcc_mean": audio_features['mfcc_mean']
    })
    song.save()


def get_or_create_playlist(playlist_id, request, sp: Spotify):
    playlist = Playlist.objects.filter(spotify_id=playlist_id).first()
    if not playlist:
        playlist_data = sp.playlist(playlist_id)
        playlist = Playlist.objects.create(
            user=request.user,
            name=playlist_data['name'],
            spotify_id=playlist_data['id'],
            description=playlist_data['description'],
            image_url=playlist_data['images'][0]['url'] if playlist_data['images'] else None,
            track_count=playlist_data['tracks']['total'],
        )
        # playlist.tracks.set(get_playlist_tracks(sp, playlist_id))
        playlist.save()

    return playlist


def get_user_playlists(sp: Spotify, request):
    cache_key = f'user_playlists_{sp.current_user()["id"]}'
    cached_playlists = cache.get(cache_key)
    if cached_playlists:
        return cached_playlists

    playlists = sp.current_user_playlists()
    result = []

    for playlist in playlists['items']:
        pl = get_or_create_playlist(playlist['id'], request, sp)
        result.append(pl)
    cache.set(cache_key, result, 3600)  # Cache for 1 hour
    return result


def get_playlist_tracks(sp: Spotify, playlist_id):
    cache_key = f"playlist_tracks_{playlist_id}"
    cached_tracks = cache.get(cache_key)
    if cached_tracks:
        return cached_tracks

    results = sp.playlist_items(playlist_id)
    tracks = []

    for spotify_track in results['items']:
        track = get_or_create_track(spotify_track['track'], sp)
        tracks.append(track)

    cache.set(cache_key, tracks, 3600)  # Cache for 1 hour
    return tracks


def get_user_top_tracks(sp: Spotify):
    cache_key = f'user_top_tracks_{sp.current_user()["id"]}'
    cached_top_tracks = cache.get(cache_key)
    if cached_top_tracks:
        return cached_top_tracks
    results = sp.current_user_top_tracks(limit=15, time_range='medium_term')
    top_tracks = []

    for spotify_track in results['items']:
        track = get_or_create_track(spotify_track, sp)
        song_dict = {
            'name': track.title,
            'artist': track.artists.all().first().name,
            'album': track.album,
            'id': track.spotify_id
        }
        top_tracks.append(song_dict)

    cache.set(cache_key, top_tracks, 3600)  # Cache for 1 hour
    return top_tracks


def get_user_recently_played(sp: Spotify):
    cache_key = f'user_recently_played_{sp.current_user()["id"]}'
    cached_recently_played = cache.get(cache_key)
    if cached_recently_played:
        return cached_recently_played

    results = sp.current_user_recently_played(limit=15)
    recently_played = []

    for spotify_track in results['items']:
        track = get_or_create_track(spotify_track['track'], sp)
        track_dict = {
            'name': track.title,
            'artist': track.artists.all().first().name,
            'album': track.album,
            'id': track.spotify_id,
            'played_at': spotify_track['played_at'],
            'duration': spotify_track['track']['duration_ms']  # Add duration in milliseconds
        }
        recently_played.append(track_dict)

    cache.set(cache_key, recently_played, 3600)  # Cache for 1 hour
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

    url = f"https://www.jiosaavn.com/api.php?__call=autocomplete.get&_format=json&_marker=0&cc=in&includeMetaTags=1&query={query}"
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
    url = f"https://www.jiosaavn.com/api.php?__call=song.getDetails&cc=in&_marker=0%3F_marker%3D0&_format=json&pids={track_id}"
    response = requests.get(url)
    data = response.json()
    data = data[track_id]

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
    try:
        y, sr = librosa.load(audio_file)
    except Exception as e:
        print(f"Error loading audio file: {e}")
        return None

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
    if not preview_url or not preview_url.startswith("http"):
        return None
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

    track = Track.objects.get(spotify_id=track_id)

    # First check if we already have audio features
    if track.audio_features:
        target_features = track.audio_features
    else:
        # If no features, extract them
        search = f"{track.title} {"".join([artist.name for artist in track.artists.all()])} {track.album}".strip()
        # search = f"{track.title} {track.artists.all().first().name}"
        translated_text = translate_text(search)
        search_song = search_jiosaavn(translated_text)[0]
        target_track = get_track_details_jiosaavn(search_song['id'])

        if not track.preview_url:
            track.preview_url = target_track['preview_url']
            track.save()

        preview_file = download_preview(target_track['preview_url'], track_id)
        if not preview_file:
            return []

        target_features = extract_audio_features(preview_file)
        track.audio_features = target_features
        track.save()

    target_features_scalar = {k: float(v) for k, v in target_features.items()}

    similarities = []
    for stored_track in stored_tracks:
        try:
            stored_song = Track.objects.get(spotify_id=stored_track['id'])
            if stored_song.audio_features:
                stored_features = stored_song.audio_features
            else:
                raise Track.DoesNotExist  # Handle like song not found
        except Track.DoesNotExist:
            search = f"{stored_track['name']} {stored_track['artist']}"
            results = search_jiosaavn(search)
            if not results:
                continue

            preview_path = download_preview(results[0]['preview_url'], stored_track['id'])
            if not preview_path:
                continue

            stored_features = extract_audio_features(preview_path)

            # Save features if song exists
            try:
                stored_song = Track.objects.get(spotify_id=stored_track['id'])
                stored_song.audio_features = stored_features
                stored_song.save()
            except Track.DoesNotExist:
                pass

        stored_features_scalar = {k: float(v) for k, v in stored_features.items()}
        target_vector = np.array(list(target_features_scalar.values()))
        stored_vector = np.array(list(stored_features_scalar.values()))

        similarity = cosine_similarity(
            target_vector.reshape(1, -1),
            stored_vector.reshape(1, -1)
        )[0][0]

        similarities.append({
            'id': stored_track['id'],
            'similarity': similarity
        })

    recommendations = sorted(similarities, key=lambda x: x['similarity'], reverse=True)[:limit]
    cache.set(cache_key, recommendations, 3600)
    return recommendations


def create_playlist_spotify(sp: Spotify, name, description=""):
    user_id = sp.current_user()['id']
    playlist = sp.user_playlist_create(user_id, name, public=False, description=description)
    return playlist


def add_tracks_to_playlist_spotify(sp: Spotify, playlist_id, track_ids):
    track_ids = [f"spotify:track:{track_id}" for track_id in track_ids]
    sp.playlist_add_items(playlist_id, track_ids)


def remove_tracks_from_playlist_spotify(sp: Spotify, playlist_id, track_ids):
    track_ids = [f"spotify:track:{track_id}" for track_id in track_ids]
    sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)


def delete_playlist_spotify(sp: Spotify, playlist_id):
    sp.current_user_unfollow_playlist(playlist_id)


def calculate_listening_time(sp: Spotify, recently_played):
    cache_key = f"listening_time_{sp.current_user()['id']}"
    cached_listening_time = cache.get(cache_key)
    if cached_listening_time:
        return cached_listening_time
    if not recently_played:
        return 0.0
    total_ms = sum(track['duration'] for track in recently_played) / (1000 * 60 * 60)  # Convert to hours
    cache.set(cache_key, total_ms, 3600)  # Cache for 1 hour
    return total_ms


def get_favorite_genre(sp: Spotify, top_tracks):
    cache_key = f"favorite_genre_{sp.current_user()['id']}"
    cached_genre = cache.get(cache_key)
    if cached_genre:
        return cached_genre
    if not top_tracks:
        return None
    artist_names = [track['artist'] for track in top_tracks]
    all_genres = []
    missing_artists = []
    artist_query = Q()
    for name in artist_names:
        artist_query |= Q(name__iexact=name)
    existing_artists = Artist.objects.filter(artist_query).prefetch_related('genres')
    artist_genres_map = {artist.name.lower(): list(artist.genres.values_list('name', flat=True))
                         for artist in existing_artists}

    for artist_name in artist_names:
        if artist_name.lower() in artist_genres_map:
            all_genres.extend(artist_genres_map[artist_name.lower()])
        else:
            missing_artists.append(artist_name)

    if missing_artists:
        try:
            for artist_name in missing_artists:
                search_results = sp.search(artist_name, type='artist', limit=1)
                if not search_results['artists']['items']:
                    continue

                artist_data = search_results['artists']['items'][0]
                genres = artist_data.get('genres', [])

                artist, created = Artist.objects.get_or_create(
                    spotify_id=artist_data['id'],
                    defaults={'name': artist_data['name']}
                )

                if created or not artist.genres.exists():
                    genre_objects = [
                        Genre.objects.get_or_create(name=genre_name)[0]
                        for genre_name in genres
                    ]
                    artist.genres.set(genre_objects)

                all_genres.extend(genres)

        except Exception as e:
            print(f"Error fetching artist genres from Spotify: {e}")

    if not all_genres:
        return None

    most_common_genre = Counter(all_genres).most_common(1)[0][0]
    cache.set(cache_key, most_common_genre, 3600)  # Cache for 1 hour

    return most_common_genre

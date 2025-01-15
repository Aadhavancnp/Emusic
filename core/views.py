from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from core.forms import ContactForm
from core.models import FAQItem
from music.models import Playlist, Track
from music.spotify import get_recommendations, get_spotify_client, get_user_playlists, get_user_top_tracks, \
    get_user_recently_played, calculate_listening_time, get_favorite_genre
from subscription.models import Subscription
from users.models import UserActivity


def home(request):
    return render(request, "core/home.html")


def about_us(request):
    return render(request, 'core/about_us.html')


def faq_list(request):
    faqs = FAQItem.objects.all()
    return render(request, 'core/faq_list.html', {'faqs': faqs})


def contact_us(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your message has been sent successfully!')
            return redirect('contact')
    else:
        form = ContactForm()
    return render(request, 'core/contact_us.html', {'form': form})


@login_required(login_url="/users/login/")
# @cache_page(900)
def dashboard(request):
    user = request.user
    sp = get_spotify_client(request)

    get_user_playlists(sp, request)
    top_tracks = get_user_top_tracks(sp)
    recently_played = get_user_recently_played(sp)

    most_repeat = Counter([track['id'] for track in recently_played]).most_common(1)[0][0]
    most_repeat = [track for track in recently_played if track['id'] == most_repeat][0]

    recently_played = list({track['id']: track for track in recently_played}.values())
    recently_played.append(most_repeat)

    recommendation_ids = get_recommendations(recently_played[0]['id'], top_tracks + recently_played)
    recommendation_ids = list({track['id']: track for track in recommendation_ids}.values())
    recommended_tracks = [Track.objects.get(spotify_id=track['id']) for track in recommendation_ids]

    listening_time = calculate_listening_time(sp, recently_played)
    favorite_genre = get_favorite_genre(sp, top_tracks)
    recent_activities = UserActivity.objects.filter(user=user).order_by('-timestamp')[:5]
    subscription = Subscription.objects.filter(user=user).first()
    user_playlists = Playlist.objects.filter(user=user)

    context = {
        'recommended_tracks': recommended_tracks,
        'recent_activities': recent_activities,
        'subscription': subscription,
        'user_playlists': user_playlists,
        'listening_time': listening_time,
        'favorite_genre': favorite_genre,
        'playlist_count': len(user_playlists),
    }
    return render(request, 'core/dashboard.html', context)

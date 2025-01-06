from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page

from core.forms import ContactForm
from core.models import FAQItem
from music.models import Playlist
from music.spotify import get_recommendations, get_spotify_client, get_user_playlists, get_user_top_tracks, \
    get_user_recently_played, calculate_listening_time, get_favorite_genre, search_jiosaavn
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
# @cache_page(60 * 15)
def dashboard(request):
    user = request.user
    sp = get_spotify_client(request)

    playlists = get_user_playlists(sp)
    top_tracks = get_user_top_tracks(sp)
    recently_played = get_user_recently_played(sp)

    # Store playlists in the database
    for playlist in playlists:
        Playlist.objects.update_or_create(
            user=user,
            spotify_id=playlist['id'],
            defaults={'name': playlist['name']}
        )

    recently_played_jiosaavn = search_jiosaavn(recently_played[0]['name'])
    recommended_songs = get_recommendations(recently_played_jiosaavn[0]['id'], top_tracks + recently_played)
    listening_time = calculate_listening_time(recently_played)
    favorite_genre = get_favorite_genre(sp, top_tracks)

    recent_activities = UserActivity.objects.filter(user=user).order_by('-timestamp')[:5]
    subscription = Subscription.objects.filter(user=user).first()
    user_playlists = Playlist.objects.filter(user=user)

    recommended_songs = list({v['id']: v for v in recommended_songs}.values())
    context = {
        'recommended_songs': recommended_songs,
        'recent_activities': recent_activities,
        'subscription': subscription,
        'playlists': playlists,
        'user_playlists': user_playlists,
        'listening_time': listening_time,
        'favorite_genre': favorite_genre,
        'playlist_count': len(playlists),
    }
    return render(request, 'core/dashboard.html', context)

from django.db import models
from django.utils import timezone

from users.models import CustomUser


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Artist(models.Model):
    name = models.CharField(max_length=100)
    monthly_listeners = models.IntegerField(default=0)
    spotify_id = models.CharField(max_length=100, unique=True)
    image_url = models.URLField(max_length=500)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Song(models.Model):
    title = models.CharField(max_length=200)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    spotify_id = models.CharField(max_length=100, unique=True)
    album = models.CharField(max_length=200)
    duration = models.DurationField(null=True)
    preview_url = models.URLField(null=True, blank=True)
    play_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.title} - {self.artist.name}"

    class Meta:
        ordering = ['-created_at']


class Playlist(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    tracks = models.ManyToManyField(Song, related_name='playlists')
    spotify_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    class Meta:
        ordering = ['-updated_at']

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
    spotify_id = models.CharField(max_length=100, unique=True, db_index=True)
    genres = models.ManyToManyField(Genre, related_name='artists')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Track(models.Model):
    title = models.CharField(max_length=200, db_index=True)
    artists = models.ManyToManyField(Artist, related_name='tracks')
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    spotify_id = models.CharField(max_length=100, unique=True, db_index=True)
    album = models.CharField(max_length=200)
    duration = models.DurationField(null=True)
    image_url = models.URLField(null=True, blank=True)
    preview_url = models.URLField(null=True, blank=True)
    popularity = models.IntegerField(default=0)
    release_date = models.DateField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
    audio_features = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {', '.join([artist.name for artist in self.artists.all()])}"

    class Meta:
        ordering = ['-created_at']


class Playlist(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    spotify_id = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(null=True, blank=True)
    tracks = models.ManyToManyField(Track, related_name='playlists')
    track_count = models.IntegerField(default=0)
    image_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"

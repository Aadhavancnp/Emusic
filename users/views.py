from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required

from .forms import SignUpForm, LoginForm, UserProfileForm, UserPreferencesForm
from .models import UserActivity


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            user.refresh_from_db()
            user.userprofile.profile_picture = form.cleaned_data.get('profile_picture')
            user.userprofile.save()
            login(request, user)
            messages.success(request, 'Account created successfully. Welcome to E-Music!')
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'users/signup.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'You have successfully logged in.')
            return redirect('dashboard')
    else:
        form = LoginForm()
    return render(request, 'users/login.html', {'form': form})


def user_logout(request):
    logout(request)
    messages.success(request, 'You have successfully logged out.')
    return redirect('login')


@login_required
def user_activities(request):
    activities = UserActivity.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'users/user_activities.html', {'activities': activities})


@login_required
def profile(request):
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user.userprofile)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('profile')
    else:
        profile_form = UserProfileForm(instance=request.user.userprofile)
    return render(request, 'users/profile.html', {
        'profile_form': profile_form
    })


@login_required
def settings(request):
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            # Save preferences to user's session or database
            request.session['theme'] = form.cleaned_data['theme']
            request.session['language'] = form.cleaned_data['language']
            return redirect('settings')
    else:
        # Load current preferences
        initial_data = {
            'theme': request.session.get('theme', 'light'),
            'language': request.session.get('language', 'en'),
        }
        form = UserPreferencesForm(initial=initial_data)
    return render(request, 'users/settings.html', {'form': form})
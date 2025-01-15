from django.contrib import admin

from subscription.models import Subscription, SubscriptionPlan

# Register your models here.
admin.site.register(Subscription)
admin.site.register(SubscriptionPlan)

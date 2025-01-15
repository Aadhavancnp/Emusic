from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import post_save
from users.models import CustomUser


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    duration_days = models.IntegerField(help_text="Duration in days")
    description = models.TextField()
    features = models.TextField()

    def __str__(self):
        return self.name


class Subscription(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"


@receiver(post_save, sender=CustomUser)
def create_user_subscription(sender, instance, created, **kwargs):
    # Check if user has no subscription
    try:
        Subscription.objects.get(user=instance)
    except Subscription.DoesNotExist:
        try:
            free_plan = SubscriptionPlan.objects.get(name='Free')
            Subscription.objects.create(
                user=instance,
                plan=free_plan,
                end_date=timezone.now() + timedelta(days=free_plan.duration_days)
            )
        except SubscriptionPlan.DoesNotExist:
            pass

# capyExtended/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


# Creation of the custom user model from DRF itself!
class CustomUser(AbstractUser):
    # Override email to be unique and required
    email = models.EmailField(unique=True)
    profile_image = models.ImageField(
        upload_to='profile_pics/', null=True, blank=True
    )
    email_confirmed = models.BooleanField(default=False)
    confirmation_token = models.UUIDField(
        null=True,  # Allows null value in the database
        blank=True,  # Allows blank field in forms/admin
        editable=False  # Should not be directly editable in admin
    )
    token_created_at = models.DateTimeField(
        null=True,  # Allows null value
        blank=True,  # Allows blank field
        editable=False  # Not editable
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email


class Item(models.Model):
    # Use settings.AUTH_USER_MODEL to reference the user model
    # Remember!(Good practice): use settings.AUTH_USER_MODEL to reference
    # the user model
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='items'
    )
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    # if the item is public or private (requirement!)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # optional for debugging
    def __str__(self) -> str:
        return str(self.title)

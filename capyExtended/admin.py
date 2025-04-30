# capyExtended/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Item

# To customize how CustomUser appears in the Admin


class CustomUserAdmin(UserAdmin):
    # Keeps most of the default UserAdmin settings
    # Adds our custom fields to the fieldsets
    # We copy the default fieldsets and add ours
    # Ensure fieldsets is not None and convert to list
    _fieldsets = list(UserAdmin.fieldsets or ())
    _fieldsets.append(
        # Adds a new section called 'Custom Fields'
        ('Campos Customizados',
         {'fields': ('profile_image', 'email_confirmed')})
    )
    fieldsets = _fieldsets
    # Adds the custom fields to the user creation form
    # Ensure add_fieldsets is not None and convert to list
    _add_fieldsets = list(UserAdmin.add_fieldsets or ())
    _add_fieldsets.append(
        ('Campos Customizados',
         {'fields': ('profile_image', 'email_confirmed')})
    )
    add_fieldsets = _add_fieldsets

    # Adds extra columns to the user list in the admin
    list_display = (
        'email', 'username', 'first_name', 'last_name', 'is_staff',
        'email_confirmed'
    )
    # Adds 'email_confirmed' to the side filters
    # Ensure list_filter is not None and convert to list
    _list_filter = list(UserAdmin.list_filter or ())
    _list_filter.append('email_confirmed')
    # Convert back to tuple if needed, or keep as list
    list_filter = tuple(_list_filter)
    # Allows searching by custom fields (defaults already include email, etc.)
    # Ensure search_fields is not None
    # Do not add existing fields
    search_fields = UserAdmin.search_fields or ()


# Registers the Item model in the Admin (with default configuration)
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    # Shows these fields in the item list
    list_display = ('title', 'owner_email_display', 'is_public', 'created_at')
    # Adds side filters
    list_filter = ('is_public', 'owner', 'created_at')
    # Allows searching by title, description, and owner data
    search_fields = (
        'title', 'description', 'owner__email', 'owner__username'
    )
    # Defines fields that are read-only in the edit form
    readonly_fields = ('created_at',)

    # Method to display the owner's email in the list in a friendly way
    def owner_email_display(self, obj):
        return obj.owner.email
    # Column name
    owner_email_display.short_description = 'Owner Email'  # type: ignore

# Registers CustomUser using the custom admin class


admin.site.register(CustomUser, CustomUserAdmin)

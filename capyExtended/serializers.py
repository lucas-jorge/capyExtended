from rest_framework import serializers
# Import password validation
from django.contrib.auth.password_validation import (
    validate_password as django_validate_password
)
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import CustomUser, Item


# Serializer used to expose user data in the API
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        # Fields exposed in the API
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'profile_image', 'email_confirmed'
        ]
        # Read-only
        read_only_fields = ['id', 'email_confirmed']


# Specific serializer for the registration process
class RegisterSerializer(serializers.ModelSerializer):
    # Adds extra fields that are not directly in the model, but are
    # necessary for registration
    password = serializers.CharField(
        write_only=True, required=True, style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True, required=True, label='Confirm password',
        style={'input_type': 'password'}
    )

    class Meta:
        model = CustomUser
        # Fields required to create a new user via API
        fields = [
            'username', 'email', 'first_name', 'last_name', 'password',
            'password2', 'profile_image'
        ]
        extra_kwargs = {
            # Ensures first and last name are sent during registration
            'first_name': {'required': True},
            'last_name': {'required': True},
            # Profile image is optional during registration
            'profile_image': {'required': False}
        }

    # Extra validation: check if passwords match
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            # Associates the error with the 'password2' field for clarity
            raise serializers.ValidationError(
                {"password2": "Password fields didn't match."}
            )
        # (Optional) Validate if email/username already exist
        if CustomUser.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError(
                {"email": "A user with that email already exists."}
            )
        if CustomUser.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError(
                {"username": "A user with that username already exists."}
            )
        return attrs

    # Method called when the serializer needs to create a new object (user)
    def create(self, validated_data):
        # Removes the 'password2' field which does not go to the database
        validated_data.pop('password2')
        # Gets the password to handle separately (hashing)
        password = validated_data.pop('password')
        # Creates the user instance with the remaining validated data
        user = CustomUser(**validated_data)
        # Sets the password using the method that performs hashing (encryption)
        user.set_password(password)
        # Ensures the email is not confirmed upon registration
        user.email_confirmed = False
        # Saves the user to the database
        user.save()
        return user


# Serializer for Items
class ItemSerializer(serializers.ModelSerializer):
    # Extra field to show the owner's email (read-only)
    # Makes it easier for API consumers not to have to make another request
    # for the owner's ID
    owner_email = serializers.ReadOnlyField(source='owner.email')

    class Meta:
        model = Item
        # Item fields that will be exposed in the API
        fields = [
            'id', 'title', 'description', 'is_public', 'created_at', 'owner',
            'owner_email'
        ]
        # fields defined by the system or that should not be sent
        # directly by the user
        read_only_fields = ['id', 'created_at', 'owner', 'owner_email']
        # optional
        extra_kwargs = {
            'description': {'required': False}
        }


# New Serializer for Password Change
# pylint: disable=abstract-method
class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for the password change process.

    Requires the old password and the new password (with confirmation).
    """
    old_password = serializers.CharField(
        required=True,
        write_only=True,  # Don't want to read/expose the old password
        style={'input_type': 'password'}
    )
    new_password1 = serializers.CharField(
        required=True,
        write_only=True,  # Don't expose the new password
        style={'input_type': 'password'},
        help_text='Your new password.'  # Help text for API documentation
    )
    new_password2 = serializers.CharField(
        required=True,
        write_only=True,  # Don't expose the confirmation
        style={'input_type': 'password'},
        help_text='Confirm your new password.'  # Help text for API documentation
    )

    def validate(self, attrs):

        # 1. Checks if the new password and confirmation are the same
        if attrs['new_password1'] != attrs['new_password2']:
            # The error is associated with the 'new_password2' field for clarity
            raise serializers.ValidationError(
                {"new_password2": "The new passwords do not match."}
            )

        # 2. Validates the strength of the new password using
        # Django validators
        # Gets the user from the context passed by the View
        user = self.context['request'].user
        try:
            # Use attrs here
            django_validate_password(password=attrs['new_password1'], user=user)
        except DjangoValidationError as e:
            # Converts the Django validation error to a DRF error
            raise serializers.ValidationError(
                {"new_password1": list(e.messages)}
            )
        return attrs  # Retorna attrs


# --- New Serializer to Validate Confirmation Token ---
# pylint: disable=abstract-method
class ValidateConfirmationSerializer(serializers.Serializer):
    """
    Simple serializer to receive the UUID token sent by the user
    to validate the email.
    """
    token = serializers.UUIDField(
        required=True,
        help_text="The UUID token received for confirmation."
    )

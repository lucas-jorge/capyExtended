# capyExtended/views.py

import uuid
from datetime import timedelta

from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, filters, status, serializers
from rest_framework.request import Request  # For type hinting request
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token # Import Token model

# Import Models
from .models import CustomUser, Item

# Import Serializers
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    ItemSerializer,
    ChangePasswordSerializer,
    ValidateConfirmationSerializer,
)

# Import Permissions
from .permissions import IsEmailConfirmed


# Authentication and Registration Views

class RegisterView(generics.CreateAPIView):
    """
    Endpoint for registering new users. Open to everyone.
    Returns the created user's data using UserSerializer.
    """
    queryset = CustomUser.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request: Request,
               *args: tuple, **kwargs: dict) -> Response:
        """
        Creates a user and returns their data via UserSerializer.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Assume serializer.instance is set after perform_create
        assert isinstance(serializer.instance, CustomUser)
        user_instance: CustomUser = serializer.instance
        response_serializer = UserSerializer(
            user_instance, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED,
            headers=headers
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    Endpoint to view (GET) and update (PUT/PATCH) the authenticated
    user's profile.
    """
    serializer_class = UserSerializer
    # Requires authentication
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self) -> AbstractBaseUser:
        """
        Returns the authenticated user associated with the request.
        """
        # IsAuthenticated ensures request.user is not AnonymousUser
        assert isinstance(self.request.user, CustomUser)
        return self.request.user


class LogoutView(APIView):
    """
    Endpoint to log out the authenticated user by deleting their token.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request: Request) -> Response:
        """
        Deletes the user's authentication token.
        """
        # request.user is guaranteed to be authenticated due to permission_classes
        if request.user.auth_token:
            request.user.auth_token.delete()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK
            )
        return Response(
            {"detail": "No active token found."},
            status=status.HTTP_400_BAD_REQUEST
        )


# --- Items ---

class PublicItemListView(generics.ListCreateAPIView):
    """
    Endpoint to list public items (GET) and create new items (POST).
    GET is open, POST requires Token authentication.
    Supports pagination, search, ordering, and filtering.
    """
    serializer_class = ItemSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    pagination_class = PageNumberPagination
    page_size_query_param = 'page_size'  # Allow custom page size
    queryset = Item.objects.filter(is_public=True)

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ['owner', 'is_public']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at']
    ordering = ['-created_at']

    def perform_create(self, serializer: serializers.BaseSerializer) -> None:
        """
        Associates the item being created with the authenticated user.
        """
        serializer.save(owner=self.request.user)


# --- Change Password View ---

class ChangePasswordView(generics.UpdateAPIView):
    """Endpoint to change the authenticated user's password."""
    serializer_class = ChangePasswordSerializer
    model = CustomUser
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self) -> AbstractBaseUser:  # Removed unused queryset=None
        """
        Returns the authenticated user as the object to be "updated".
        """
        # IsAuthenticated ensures request.user is not AnonymousUser
        assert isinstance(self.request.user, CustomUser)
        return self.request.user

    def update(self, request: Request,
               *args: tuple, **kwargs: dict) -> Response:
        """
        Handles the PUT/PATCH request to change the password.
        """
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        # Ensure self.object is CustomUser after get_object()
        assert isinstance(self.object, CustomUser)
        user: CustomUser = self.object

        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        old_password = serializer.validated_data.get("old_password")

        # Additional validation for old password
        if not user.check_password(old_password):
            raise serializers.ValidationError(
                {"old_password": ["Incorrect old password."]}
            )

        # Define new password
        user.set_password(
            serializer.validated_data.get("new_password1")
        )
        user.save()

        # Return success response
        response_data = {
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "Password updated successfully",
            "data": [],
        }
        return Response(response_data)


# --- Views for e-mail confirmation ---

class RequestConfirmationEmailView(APIView):
    """
    Endpoint for a logged-in user to request a new email
    confirmation token.
    """
    permission_classes = [permissions.IsAuthenticated]

    # Removed unused *args, **kwargs
    def post(self, request: Request) -> Response:
        """
        Generates and saves a confirmation token for the user. Simulates sending.
        """
        user: CustomUser = request.user  # type: ignore

        if user.email_confirmed:
            return Response(
                {"message": "Your email is already confirmed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_token = uuid.uuid4()
        user.confirmation_token = new_token
        user.token_created_at = timezone.now()
        user.save(update_fields=['confirmation_token', 'token_created_at'])

        return Response(
            {"message": "Confirmation token generated and 'sent' (simulated). "
                        "Check the console.",
             "token": str(new_token)},
            status=status.HTTP_200_OK
        )


class ValidateConfirmationView(APIView):
    """
    Endpoint to validate the email confirmation token
    sent by the user in the request body.
    """
    permission_classes = [permissions.IsAuthenticated]

    # Removed unused *args, **kwargs
    def post(self, request: Request) -> Response:
        """
        Validates the token and confirms the user's email if valid and not expired.
        """
        user: CustomUser = request.user  # type: ignore
        serializer = ValidateConfirmationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        provided_token: uuid.UUID = serializer.validated_data['token']

        if user.email_confirmed:
            return Response(
                {"message": "Este e-mail já foi confirmado anteriormente."},
                status=status.HTTP_200_OK
            )

        if not user.confirmation_token or not user.token_created_at:
            return Response(
                {"error": "Nenhum processo de confirmação pendente encontrado. "
                          "Solicite um novo token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify token expiration
        expiration_duration = timedelta(hours=24)
        now = timezone.now()
        is_expired = now > user.token_created_at + expiration_duration

        if is_expired:
            user.confirmation_token = None
            user.token_created_at = None
            user.save(update_fields=['confirmation_token', 'token_created_at'])
            return Response(
                {"error": "Confirmation token expired. "
                          "Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Compare tokens
        if str(provided_token) == str(user.confirmation_token):
            user.email_confirmed = True
            user.confirmation_token = None
            user.token_created_at = None
            user.save(
                update_fields=[
                    'email_confirmed', 'confirmation_token', 'token_created_at'
                ]
            )
            return Response({"message": "Email confirmed successfully!"},
                            status=status.HTTP_200_OK)
        # No need for else after return
        return Response({"error": "Token de confirmação inválido."},
                        status=status.HTTP_400_BAD_REQUEST)


class RestrictedItemListView(generics.ListAPIView):
    """
    Endpoint to list restricted items (is_public=False).
    Accessible only by authenticated users AND with confirmed email.
    Supports pagination, search, ordering, and filtering (same as public list).
    """
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailConfirmed]
    queryset = Item.objects.filter(is_public=False)

    # Reused pagination and filter settings from PublicItemListView
    pagination_class = PageNumberPagination
    page_size_query_param = 'page_size'
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    filterset_fields = ['owner', 'is_public']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at']
    ordering = ['-created_at']


class LegalInfoView(APIView):
    """
    Public endpoint that returns links to the Terms of Use
    and Privacy Policy documents.
    """
    # Allow any user to access this endpoint
    permission_classes = [permissions.AllowAny]

    # Removed unused request and format arguments
    def get(self, _request: Request, _format=None) -> Response:
        """
        Responds to GET requests with predefined links.
        """
        # Links for Terms of Service and Privacy Policy
        terms_url = "https://bit.ly/42vUiep"
        privacy_url = "http://bit.ly/3Epmx6G"

        data = {
            "terms_of_service_url": terms_url,
            "privacy_policy_url": privacy_url
        }
        return Response(data, status=status.HTTP_200_OK)

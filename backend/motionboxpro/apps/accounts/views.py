from django.conf import settings
from django.contrib import auth
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import User
from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
)


class CsrfCheckedSession(SessionAuthentication):
    """
    Session auth for the public POST endpoints (login, register, password reset).
    DRF only checks the CSRF token for users who are already logged in, so without
    this a site could log a visitor into an account the attacker controls.
    """

    def authenticate(self, request):
        self.enforce_csrf(request)
        return None


def _user_data(user):
    return {
        "id": user.pk,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Sets the csrftoken cookie. The React app calls this before its first POST."""
    return Response({"detail": "CSRF cookie set."})


@api_view(["POST"])
@authentication_classes([CsrfCheckedSession])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    auth.login(request, user)

    return Response(_user_data(user), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([CsrfCheckedSession])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    auth.login(request, user)

    return Response(_user_data(user))


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    # Ends this browser's session. Sessions on the user's other devices stay open.
    auth.logout(request)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(_user_data(request.user))


@api_view(["POST"])
@authentication_classes([CsrfCheckedSession])
@permission_classes([AllowAny])
def password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()

    if user is not None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"

        send_mail(
            subject="Reset your password",
            message=(
                "Open this link to choose a new password:\n\n"
                f"{link}\n\n"
                "If you didn't ask for this, you can ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

    # Same answer whether or not the email has an account, so this can't be used to find accounts
    return Response({"detail": "If that email has an account, a reset link is on its way."})


@api_view(["POST"])
@authentication_classes([CsrfCheckedSession])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]

    # Django logs out the user's other sessions on their next request, because each session
    # stores a hash of the password it was created with.
    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])

    return Response({"detail": "Your password has been changed. You can log in now."})

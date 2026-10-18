from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "first_name", "last_name")

    def validate(self, attrs):
        candidate = User(email=attrs.get("email", ""), first_name=attrs.get("first_name", ""),
                         last_name=attrs.get("last_name", ""))
        validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(request=self.context.get("request"),
                            username=attrs["email"], password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Wrong email or password.")

        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        invalid = "This reset link is invalid or has expired. Request a new one."
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(attrs["uid"])))
        except (User.DoesNotExist, TypeError, ValueError, OverflowError):
            raise serializers.ValidationError(invalid)

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(invalid)

        validate_password(attrs["new_password"], user=user)
        attrs["user"] = user
        return attrs

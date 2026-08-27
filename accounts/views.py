from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .serializers import RegisterSerializer

class RegisterView(generics.CreateAPIView):
    serilizer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['username'] = user.username
        return token

class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer

    
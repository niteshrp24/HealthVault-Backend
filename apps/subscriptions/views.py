from rest_framework import serializers, generics
from rest_framework.permissions import AllowAny
from apps.accounts.models import SubscriptionPlan
from apps.core.permissions import IsAdminPortal


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubscriptionPlanListCreateView(generics.ListCreateAPIView):
    serializer_class = SubscriptionPlanSerializer
    queryset = SubscriptionPlan.objects.all()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminPortal()]


class SubscriptionPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminPortal]
    serializer_class = SubscriptionPlanSerializer
    queryset = SubscriptionPlan.objects.all()

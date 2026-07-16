from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.core.permissions import IsAdminPortal, IsLabPortal
from apps.notifications.models import Notification
from apps.accounts.models import LabHospital


# ─── Serializers ─────────────────────────────────────────────────────────────

class NotificationCreateSerializer(serializers.Serializer):
    lab_id = serializers.UUIDField()
    message = serializers.CharField(min_length=5)
    channels = serializers.MultipleChoiceField(
        choices=Notification.Channel.choices,
        allow_empty=False,
    )

    def validate_lab_id(self, value):
        try:
            return LabHospital.objects.get(id=value)
        except LabHospital.DoesNotExist:
            raise serializers.ValidationError('Lab not found.')


class NotificationListSerializer(serializers.ModelSerializer):
    lab_name = serializers.CharField(source='sent_to_lab.name', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'lab_name', 'message', 'channel',
            'status', 'error_detail', 'created_at',
        ]


# ─── Views ───────────────────────────────────────────────────────────────────

class AdminSendNotificationView(APIView):
    """Admin sends a message to a lab via one or more channels."""
    permission_classes = [IsAdminPortal]

    def post(self, request):
        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lab = serializer.validated_data['lab_id']
        message = serializer.validated_data['message']
        channels = serializer.validated_data['channels']
        admin = request.user

        created = []
        for channel in channels:
            notif = Notification.objects.create(
                sent_by=admin,
                sent_to_lab=lab,
                message=message,
                channel=channel,
            )
            created.append(notif)
            # Dispatch each channel async
            from apps.notifications.tasks import dispatch_notification_task
            dispatch_notification_task.delay(str(notif.id))

        return Response(
            NotificationListSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class AdminNotificationListView(generics.ListAPIView):
    """Admin lists all notifications sent, filterable by lab."""
    permission_classes = [IsAdminPortal]
    serializer_class = NotificationListSerializer

    def get_queryset(self):
        qs = Notification.objects.select_related('sent_to_lab')
        lab_id = self.request.query_params.get('lab_id')
        if lab_id:
            qs = qs.filter(sent_to_lab_id=lab_id)
        return qs


class LabNotificationListView(generics.ListAPIView):
    """Lab sees its own in-app notifications."""
    permission_classes = [IsLabPortal]
    serializer_class = NotificationListSerializer

    def get_queryset(self):
        return Notification.objects.filter(
            sent_to_lab=self.request.user,
            channel=Notification.Channel.INAPP,
        )

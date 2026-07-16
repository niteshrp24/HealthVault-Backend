from apps.accounts.models import SubscriptionPlan

# SubscriptionPlan model lives in accounts to avoid circular imports
# since LabHospital FKs into it. Re-export for convenience.
__all__ = ['SubscriptionPlan']

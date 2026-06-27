from tortoise import fields, migrations
from tortoise.migrations import operations as ops

from app.models import SubscriptionStatus


class Migration(migrations.Migration):
    dependencies = [("models", "0004_auto_20260507_0026")]

    initial = False

    operations = [
        ops.AlterField(
            model_name="OwnerSubscription",
            name="status",
            field=fields.CharEnumField(
                default=SubscriptionStatus.INCOMPLETE,
                description="TRIALING: trialing\nACTIVE: active\nPAST_DUE: past_due\nCANCELED: canceled\nINCOMPLETE: incomplete",
                enum_type=SubscriptionStatus,
                max_length=10,
            ),
        ),
        ops.RunSQL(
            sql="ALTER TABLE owner_subscriptions ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE",
            reverse_sql="ALTER TABLE owner_subscriptions DROP COLUMN IF EXISTS cancel_at_period_end",
        ),
        ops.RunSQL(
            sql="ALTER TABLE payments ADD COLUMN IF NOT EXISTS locale VARCHAR(10) NOT NULL DEFAULT 'en'",
            reverse_sql="ALTER TABLE payments DROP COLUMN IF EXISTS locale",
        ),
    ]

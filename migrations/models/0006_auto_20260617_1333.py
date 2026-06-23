from tortoise import fields, migrations
from tortoise.migrations import operations as ops

from app.models import PaymentStatus


class Migration(migrations.Migration):
    dependencies = [("models", "0005_auto_20260616_2120")]

    initial = False

    operations = [
        # NOTE: makemigrations also re-generated AddField ops for
        # OwnerSubscription.cancel_at_period_end and Payment.locale. Those
        # columns were added by migration 0005 via raw RunSQL (which the
        # model-state tracker cannot see), so they already exist in the
        # database. Their AddField ops are intentionally omitted here to avoid
        # DuplicateColumnError — only the genuine refund changes remain.
        ops.AlterField(
            model_name="Payment",
            name="status",
            field=fields.CharEnumField(
                default=PaymentStatus.PENDING,
                description="PENDING: pending\nPAID: paid\nREFUNDED: refunded\nPARTIALLY_REFUNDED: partially_refunded\nFAILED: failed",
                enum_type=PaymentStatus,
                max_length=18,
            ),
        ),
        ops.AddField(
            model_name="Payment",
            name="refunded_amount",
            field=fields.DecimalField(null=True, max_digits=10, decimal_places=2),
        ),
    ]

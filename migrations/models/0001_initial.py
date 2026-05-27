from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models import PaymentStatus
from uuid import uuid4
from tortoise import fields

class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name='OwnerStripeAccount',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('owner_id', fields.UUIDField(unique=True)),
                ('stripe_account_id', fields.CharField(unique=True, max_length=255)),
                ('transfers_active', fields.BooleanField(default=False)),
                ('verified', fields.BooleanField(default=False)),
                ('requirements_outstanding', fields.BooleanField(default=False)),
                ('requirements_eventually_due', fields.BooleanField(default=False)),
            ],
            options={'table': 'owner_stripe_accounts', 'app': 'models', 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='Payment',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('booking_id', fields.UUIDField()),
                ('user_id', fields.UUIDField()),
                ('property_owner_id', fields.UUIDField()),
                ('stripe_session_id', fields.CharField(unique=True, max_length=255)),
                ('stripe_payment_intent_id', fields.CharField(null=True, max_length=255)),
                ('amount', fields.DecimalField(max_digits=10, decimal_places=2)),
                ('currency', fields.CharField(default='EUR', max_length=3)),
                ('status', fields.CharEnumField(default=PaymentStatus.PENDING, description='PENDING: pending\nPAID: paid\nREFUNDED: refunded\nFAILED: failed', enum_type=PaymentStatus, max_length=8)),
                ('updated_at', fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={'table': 'payments', 'app': 'models', 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
    ]

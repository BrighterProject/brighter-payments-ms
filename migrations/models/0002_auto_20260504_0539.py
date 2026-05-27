from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models import SubscriptionPlanSlug, SubscriptionStatus
from tortoise.fields.base import OnDelete
from uuid import uuid4
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0001_initial')]

    initial = False

    operations = [
        ops.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('slug', fields.CharEnumField(unique=True, description='STARTER: starter\nBASIC: basic\nPRO: pro\nBUSINESS: business\nENTERPRISE: enterprise', enum_type=SubscriptionPlanSlug, max_length=10)),
                ('name', fields.CharField(max_length=100)),
                ('max_listings', fields.IntField()),
                ('price_eur_cents', fields.IntField()),
                ('stripe_price_id', fields.CharField(null=True, max_length=255)),
                ('is_active', fields.BooleanField(default=True)),
            ],
            options={'table': 'subscription_plans', 'app': 'models', 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='OwnerSubscription',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('owner_id', fields.UUIDField(unique=True)),
                ('plan', fields.ForeignKeyField('models.SubscriptionPlan', source_field='plan_id', db_constraint=True, to_field='id', related_name='subscriptions', on_delete=OnDelete.RESTRICT)),
                ('status', fields.CharEnumField(default=SubscriptionStatus.INCOMPLETE, description='TRIALING: trialing\nACTIVE: active\nPAST_DUE: past_due\nCANCELLED: cancelled\nINCOMPLETE: incomplete', enum_type=SubscriptionStatus, max_length=10)),
                ('stripe_customer_id', fields.CharField(null=True, max_length=255)),
                ('stripe_subscription_id', fields.CharField(null=True, unique=True, max_length=255)),
                ('current_period_end', fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                ('cancelled_at', fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
            ],
            options={'table': 'owner_subscriptions', 'app': 'models', 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
    ]

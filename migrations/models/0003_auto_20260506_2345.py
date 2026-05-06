from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models import BankTransferStatus
from uuid import uuid4
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0002_auto_20260504_0539')]

    initial = False

    operations = [
        ops.CreateModel(
            name='BankTransferPayment',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('booking_id', fields.UUIDField()),
                ('user_id', fields.UUIDField()),
                ('property_owner_id', fields.UUIDField()),
                ('amount', fields.DecimalField(max_digits=10, decimal_places=2)),
                ('currency', fields.CharField(default='EUR', max_length=3)),
                ('status', fields.CharEnumField(default=BankTransferStatus.PENDING, description='PENDING: pending\nCONFIRMED: confirmed\nCANCELLED: cancelled', enum_type=BankTransferStatus, max_length=9)),
                ('bank_iban', fields.CharField(max_length=34)),
                ('bank_bic', fields.CharField(max_length=11)),
                ('bank_name', fields.CharField(max_length=100)),
                ('account_holder', fields.CharField(max_length=200)),
                ('reference', fields.CharField(max_length=50)),
                ('updated_at', fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={'table': 'bank_transfer_payments', 'app': 'models', 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='OwnerBankAccount',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('owner_id', fields.UUIDField(unique=True)),
                ('iban', fields.CharField(max_length=34)),
                ('bic', fields.CharField(null=True, max_length=11)),
                ('bank_name', fields.CharField(null=True, max_length=100)),
                ('account_holder', fields.CharField(max_length=200)),
                ('updated_at', fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={'table': 'owner_bank_accounts', 'app': 'models', 'pk_attr': 'id', 'table_description': "Owner's personal bank account used for bank-transfer bookings."},
            bases=['AbstractModel'],
        ),
    ]

from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0003_auto_20260506_2345')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Payment',
            name='locale',
            field=fields.CharField(default='en', max_length=10),
        ),
    ]

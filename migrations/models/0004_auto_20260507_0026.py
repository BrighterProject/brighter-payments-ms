from tortoise import migrations


class Migration(migrations.Migration):
    dependencies = [('models', '0003_auto_20260506_2345')]

    initial = False

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "payments"
                ADD COLUMN IF NOT EXISTS "locale" VARCHAR(10) NOT NULL DEFAULT 'en';
            """,
            reverse_sql='ALTER TABLE "payments" DROP COLUMN IF EXISTS "locale";',
        ),
    ]

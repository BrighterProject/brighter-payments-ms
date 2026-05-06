from tortoise.migrations import Migration, SQLOperation


class Migration(Migration):
    dependencies = [('models', '0003_auto_20260506_2345')]

    initial = False

    operations = [
        SQLOperation('ALTER TABLE "payments" ADD COLUMN IF NOT EXISTS "locale" VARCHAR(10) NOT NULL DEFAULT \'en\';', []),
    ]

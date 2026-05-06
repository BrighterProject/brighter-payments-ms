from tortoise.migrations import Migration, RunPython


async def add_locale(db) -> None:
    await db.execute_script(
        'ALTER TABLE "payments" ADD COLUMN IF NOT EXISTS "locale" VARCHAR(10) NOT NULL DEFAULT \'en\';'
    )


async def drop_locale(db) -> None:
    await db.execute_script('ALTER TABLE "payments" DROP COLUMN IF EXISTS "locale";')


class Migration(Migration):
    dependencies = [('models', '0003_auto_20260506_2345')]

    initial = False

    operations = [
        RunPython(add_locale, drop_locale),
    ]

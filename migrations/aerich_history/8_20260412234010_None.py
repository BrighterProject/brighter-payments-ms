from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "payments" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "booking_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "property_owner_id" UUID NOT NULL,
    "stripe_session_id" VARCHAR(255) NOT NULL UNIQUE,
    "stripe_payment_intent_id" VARCHAR(255),
    "amount" DECIMAL(10,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'EUR',
    "status" VARCHAR(8) NOT NULL DEFAULT 'pending',
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "payments"."status" IS 'PENDING: pending\nPAID: paid\nREFUNDED: refunded\nFAILED: failed';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztmG1P2zAQx79KlFdMYgjaAhWaJgUaRiZoEZRtYkyRG19bi8QOjjOoGN99tpM0bZp2pD"
    "yLvYHmf3ex72df/HBrBgyDH60do1EAVJg7xq1JUQDyR9G0apgoDHODEgTq+do3TJy0iHqR"
    "4MhTL+sjPwIpYYg8TkJBGJUqjX1ficyTjoQOcimm5CoGV7ABiCFwafj5S8qEYriBKHsML9"
    "0+AR9P9ZZg1bbWXTEKtXZ25rT2tadqrud6zI8DmnuHIzFkdOwexwSvqRhlGwAFjgTgiTRU"
    "L9OMMynpsRQEj2HcVZwLGPoo9hUM81M/pp5iYOiW1J/GZ7MCHo9RhZYo0DL3uySrPGetmq"
    "qpvQPrZKW+9UFnySIx4NqoiZh3OhAJlIRqrjlIj4NK20ViFmhLWgQJoBzqdGQBLk5D17If"
    "y0DOhJxyPsMyzBm+5ZiaMgfcof4oHcEFjLvOkX3atY6OVSZBFF35GpHVtZWlptVRQV1Jho"
    "TJ+kgKZ/wS47vTPTDUo3HeadvFgRv7dc9N1ScUC+ZSdu0iPDHZMjUDIz3zge0xdilTd6tV"
    "ynTUY1bM0w/mQwok5xZHwCtCmwh5j8RCzkLgYuSya1qZXWnwe6SoGgnBjSCKZPulFPeGiJ"
    "dTLA0uUJQ+T7PSPfATHKAb1wc6EEP5WNvcXIDzm3WiiUqvwoe1nZpqia0UbbprcWXL+t8y"
    "hEvfsRToFONzLnZPTxoFLKZlOwnwSID8crR5UHETkUStpdFvrvpb9p5zZB2ubKyv1jRFuT"
    "0gAib5NtaLCL2Yc6DeqMrknIx5nKq/DzfTPjt5wH52ejrW7zEZ63OnYn225JGIo3KGNo0D"
    "zdGR/UHUg5Jiz6KfkWYIFCteM0TNY7vdctpfdozU5YIeW05LPiKCL+iJvX/WbtnymYM8cm"
    "CQ2r7lHCqlj4gPyXypOB7Ne4xHc+54NIvjEYd4yWPGdOT/Y8aLHjN059WhvH85cZpUQg95"
    "l9eIY3fGwmpsnu+sKagFRQVRNNCjotiqXqY3FRZw4g3NkjuM1LK66AoD5T6v5gLDoaLC/Q"
    "VJ1szJ2Z4O2Itu5waqlY+1jcZ2o1nfajSli+7JWNleMPuddvcf9xW/gastbpXVcSLk+T7n"
    "r3+rJkujAsTU/W0C3FhfvwdA6TUXoLYVNmpMnwFmIX497bTn7NPykOJCRjxh/DF8Es0U9e"
    "sAuoCfyndqtcqwrRxZP4pE9w47u8VlSL1gV9J90YXl7i/HJW2G"
)

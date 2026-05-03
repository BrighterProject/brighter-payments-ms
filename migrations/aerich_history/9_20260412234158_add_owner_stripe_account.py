from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "owner_stripe_accounts" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "owner_id" UUID NOT NULL UNIQUE,
    "stripe_account_id" VARCHAR(255) NOT NULL UNIQUE,
    "verified" BOOL NOT NULL DEFAULT False
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "owner_stripe_accounts";"""


MODELS_STATE = (
    "eJztmG1v2jAQx79KlFdM6qoWWIemaVIo6ZapQEVhm/agyMQGrCZ2mjjr0NbvPttJSGICIv"
    "SJqrxB5Hz/2PezLz77r+5RiNzwsH9DUHDJAuwjw3FoRJj+TvurE+Ah/meN14GmA9/PfISB"
    "gbErZVT426EU2CBWSA8w5kbgiE4mwA0RN0EUOtyPYUq4lUSuK4zUEWoyzUwRwdcRshmdIj"
    "ZDAW/48YubMYHoDwrTR//KnmDkwkIUGIq+pd1mc1/aRiOrcyY9RXdj26Fu5JHM25+zGSUL"
    "9yjC8FBoRNsU8fAAQzAXhhhlEn5qikfMDSyI0GKoMDNANAGRK2Do7ycRcQQDTfYkfpof9A"
    "p4HEoEWixA89hv46iymKVVF12dfjIGtcbJKxklDdk0kI2SiH4rhYCBWCq5ZiCdAImwbcCW"
    "gXZ4C8MeKodaVCpwYSI9TP9sAzk1ZJSzFZZiTvFtx1TnMcA+cefJDK5hPLS65uXQ6F6ISL"
    "wwvHYlImNoipa6tM4Vay2eEsrzI86ixUu0r9bwkyYete/9nqlO3MJv+F0XYwIRozahNzaA"
    "ucWWWlMw3DOb2Dhhq+VJXvO42XK3abxLamTEih+3UnSnMxCUoysVKwy5zy7S0z3wx3YRmb"
    "IZf6y/ebMG5xdjIIlyL2Vp95KmetxWRPsbBZi/roRom1IXAVIONS9TWI657qG+KVX3sc1X"
    "Y7vfPy98P9rWUME46rbNQe1Y0uVOmEmz1RtypGI7nFzlvuPCMAbO1Q0IoL3UQut0le9yk1"
    "f3VAsgYCoRiThFVEntcAHmHiovK9KmtbWEHzvty4d9+bAvH3a0fODf1yseesUCoqi6z4x5"
    "+Mm8nyIiCitXXTnJSyTmB9RHAZvb21SspeKXSDGpP0MUhrz/7YrXonhfvBbRJlWLzXtG2x"
    "4PSt+xFegE42Nudg9PGnjpRZRSSSAHe8AtR5uJ1CIiVh0m6meX/R3z1Ooa57Xjo4O6chxI"
    "+TaPVIROFASIOPMqizOvuZ+s34Sbbo4Gd6hni8uxscFibKxcio3llAcsCssZmiTyJEeLjw"
    "cQB5Uke6p+RJo+IlDwWiKqX5i9jtX7+E5LXH6SC8Pq8EeA4U8yMM9GvY7JnwPEjxwQcduZ"
    "YZ0LywRgNz59V52P1gbz0Vo5Hy11PiIfbnnMKCr3x4wnPWbIwe/IJYaBAuzM9JI7jKTlYN"
    "0VBsh8duYCwyKswv0FjvfM/GpPJuxJy7mp6OV1/bj5ttlqnDRb3EWOZGF5u2b1x7dkB2vu"
    "K36jQJS4VXbHnOTxPue7X6rx1KgAMXF/ngCPj442AMi9VgKUbUqhRuUZYBni58t+b0Wdlk"
    "nUjQw7TPunuThcSurdALqGn4i3sFul2Gpd45tK9PS831a3IfGC9lPfjt/+B5BWIww="
)

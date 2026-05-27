from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" ADD "charges_enabled" BOOL NOT NULL DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" DROP COLUMN "charges_enabled";"""


MODELS_STATE = (
    "eJztmG2P2jgQx79KlFdU2lvtAm1RdTopLNlrTgusWLhW2z1FJhnA2sROE6db1PLdz3YS8g"
    "gi7BNVeYPIeP6x52dPPPYP1aU2OMHp8IGAf8N87IFmWTQkTP2g/FAJcoH/2eJ1oqjI81If"
    "YWBo6kgZFf5mIAUmihTSA025EVmikxlyAuAmGwKL+zFMCbeS0HGEkVpCTeapKST4awgmo3"
    "NgC/B5w5f/uBkTG75DkDx69+YMg2PnosC26FvaTbb0pG0yMXqX0lN0NzUt6oQuSb29JVtQ"
    "snYPQ2yfCo1omwMPDzGwM2GIUcbhJ6ZoxNzA/BDWQ7VTgw0zFDoChvrnLCSWYKDInsRP+y"
    "+1Bh6LEoEWC9A89lUUVRqztKqiq4uP2qjRevdGRkkDNvdloySirqQQMRRJJdcUpOWDCNtE"
    "rAy0x1sYdqEaal5ZgGvH0tPkzz6QE0NKOV1hCeYE335MVR6DPSTOMp7BLYzHRl+/GWv9ax"
    "GJGwRfHYlIG+uipSmty4K1EU0J5fkRZdH6JconY/xREY/K7XCgFydu7Te+VcWYUMioSeiD"
    "iezMYkusCRjumU5slLD18iSredlsedw0PiY1UmL5j1sluosF8qvRVYoLDLnPIdJTXfTddI"
    "DM2YI/Nt++3YLzX20kiXKvwtIexE3NqC2P1uLc5hCYQESQFWC7lDqAyIYvTVldIDvl8uf6"
    "wtTd1XZfm93h8Cr3Neka4wLUSb+rjxrnkjV3wkyajcG4APgb+Jh3UZdsVnZEulqJemN2n9"
    "kohWGKrPsH5NtmqYU26SbfcpPbdIsWRNBcIhJxiqji4uwaLV2ortuSpq3Fmhc5HeuzY312"
    "rM8OtD7j39d7HnrNCi2vesqMef7JfJoqLQxql7UZye9IzPOpBz5bmvscCSrFvyPFuMAPIA"
    "h4//udDvLi4+kgjzauWkzeM+x7/qp8x16gY4wvudk9P2nkJjd9hUoCLOwipxptKioWEZHq"
    "NFb/ctnf0y+MvnbVOD87aRaOAwnf9lnpKBv6PhBrWWdxZjVPk/W7cFP1yegR9Wx+ObZ2WI"
    "ytjUuxVU55xMKgmqFOQldyNPh4ELGgItkT9QvS9IDYgleJqHqtD3rG4O8PSuxyR641o8cf"
    "EbbvyEi/nAx6On/2gR85bOC2S824EpYZwvGFRt356OwwH52N89Epzkfo2XseM/LK4zHjVY"
    "8ZcvAHcomhgY+thVpxhxG3nGy7wkCpz8FcYBiE1bi/wNGemV3t8YS9ajk3F7380Txvv293"
    "Wu/aHe4iR7K2vN+y+pOLx833Fd/AFyVund0xI3m5z/nhl2o8NWpAjN1/TYDnZ2c7AOReGw"
    "HKtkKhRuUZoAzxn5vhYEOdlkqKGxm2mPJTcXBQSurDALqFn4g3t1sl2Bp97XOR6MXVsFvc"
    "hsQLuq99O776H9iklFM="
)

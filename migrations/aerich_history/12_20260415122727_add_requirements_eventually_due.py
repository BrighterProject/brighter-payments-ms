from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" ADD "requirements_eventually_due" BOOL NOT NULL DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" DROP COLUMN "requirements_eventually_due";"""


MODELS_STATE = (
    "eJztmG1v2joUx78Kyiuu1FUtsA1N05VCSe8yFago3Hu1u6vIJAewmthpYrdDG999tpOQBw"
    "Ii9IlpvGnJ8fnHPj/bsc/5rnnUATc8HTwQCG5YgH3QbZtywrQPte8aQR6IH1u8Tmoa8v3U"
    "RxoYmrhKRqW/FSqBhSKF8kATYUS27GSK3BCEyYHQFn4MUyKshLuuNFJbqsksNXGC7zhYjM"
    "6AzSEQDf/9L8yYOPANwuTRv7WmGFwnFwV2ZN/KbrGFr2zjsdm9VJ6yu4llU5d7JPX2F2xO"
    "ycqdc+ycSo1sm4EIDzFwMmHIUcbhJ6ZoxMLAAg6roTqpwYEp4q6EoX2ccmJLBjXVk/zT+l"
    "OrgMemRKLFErSIfRlFlcasrJrs6uKTPqw33/2hoqQhmwWqURHRlkqIGIqkimsK0g5Ahm0h"
    "tg60K1oY9qAcal5ZgOvE0tPkxz6QE0NKOV1hCeYE335MNRGDMyDuIp7BLYxHZs+4Gem9ax"
    "mJF4Z3rkKkjwzZ0lDWRcFaj6aEiv0R7aLVS2r/mKNPNflY+zLoG8WJW/mNvmhyTIgzahH6"
    "YCEns9gSawJGeKYTG23Yavskq3nZ3fK4aXzM1kiJ5T9upegu5igoR1cqLjAUPodIT/PQN8"
    "sFMmNz8dh4+3YLzr/1oSIqvApLux83NaK2PFpbcJtBaAGRQZaA7VDqAiIbvjTr6gLZiZA/"
    "1xem6qm2+9rsDAZXua9JxxwVoI57HWNYP1eshRNmymz2RwXA9xBg0UVVslnZEWkeaQB3HA"
    "fggejVopyFDBFHDqsa4m2vOSLfghzuxT+OXHdhORweQ339TUfwy6W8W09vM5dCaZgg+/YB"
    "BY611kIbdJPvepPX8IoWRNBMIZJxyqjiROQaLeQsaSU5StJ0si0x8SOnYy5yzEWOuciB5i"
    "Li+3orQq+YjeRVT7ljnn8ynyYj4WHlFC4j+R2J+QH1IWALa5/0t1T8O1KMk9kQwlD0v18m"
    "nBcfM+E82vjWYomeYd9aQ+k79gIdY3zJw+75SSMvqWoXbhJgYw+55WhTUfESEalOY/Uvt/"
    "u7xoXZ06/q52cnjUI6kPBtna2VbXgQALEXVRZnVvM0u34XbpoxHj7iPptfjs0dFmNz41Js"
    "rm95xHhYztAg3FMcTSILAzaUbPZE/YI0fVjVKPJEtWuj3zX7f32oxS5fybVudsUjws5XMj"
    "Qux/2uIZ4DECmHA8J2qZtX0jJFOC7eVZ2P9g7z0d44H+3ifHDf2TPNyCuPacarphlq8AdS"
    "xNAhwPZcK6lhxC0n20oYKPU5mAKGSViF+gWOzszsao8n7FWvczPZy5vGeet9q91812oLFz"
    "WSleX9ltWflCc31yvuIZBX3CqnY0bycp/zw7+qia1RAWLs/msCPD872wGg8NoIULUVLmpU"
    "5QDrED/fDPob7mmppHiQYZvVftRcHK5t6sMAuoWfjDd3WiXY6j393yLRi6tBp3gMyRd0Xr"
    "s6vvwJilGKDA=="
)

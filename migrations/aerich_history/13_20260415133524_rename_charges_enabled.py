from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" RENAME COLUMN "charges_enabled" TO "transfers_active";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" RENAME COLUMN "transfers_active" TO "charges_enabled";"""


MODELS_STATE = (
    "eJztmO9v2jgYx/8VlFec1FUtsA1Np5NCSW+ZClQU7k7bTpFJHsBqYqeJ3Q7t+N/PdhJCQs"
    "gI/cU03rTk8fON/XzsJ/bj75pHHXDD08EDgeCGBdgH3bYpJ0z7UPuuEeSB+FHidVLTkO+n"
    "PtLA0MRVMir9rVAJLBQplAeaCCOyZSdT5IYgTA6EtvBjmBJhJdx1pZHaUk1mqYkTfMfBYn"
    "QGbA6BaPjyrzBj4sA3CJNH/9aaYnCdTBTYkX0ru8UWvrKNx2b3UnnK7iaWTV3ukdTbX7A5"
    "JSt3zrFzKjWybQYiPMTAWQtDjjIOPzFFIxYGFnBYDdVJDQ5MEXclDO33KSe2ZFBTPck/rT"
    "+0CnhsSiRaLEGL2JdRVGnMyqrJri4+6sN6891vKkoaslmgGhURbamEiKFIqrimIO0AZNgW"
    "YptAu6KFYQ+KoWaVObhOLD1NfuwDOTGklNMVlmBO8O3HVBMxOAPiLuIZLGE8MnvGzUjvXc"
    "tIvDC8cxUifWTIloayLnLWejQlVORHlEWrl9T+Nkcfa/Kx9nnQN/ITt/IbfdbkmBBn1CL0"
    "wULO2mJLrAkY4ZlObJSw1fJkXfOy2fK4aXxMaqTEsh+3QnQXcxQUoysU5xgKn0Okp3nom+"
    "UCmbG5eGy8fVuC8y99qIgKr9zS7sdNjagti1b0RsIpBKEAxPA9bJLtUOoCIsVwi+Q5thOh"
    "f65vTNV9bffV2RkMrjLfk445ymEd9zrGsH6uaAsnzJTZ7I9yiO8hwKKLgkVbinZddkSaRR"
    "rAHccBeCB6tShnIUPEkcOqhrjsNUfkJcjhXvzjyHUXlsOrfjN+8KYj+OVSnq6nt2vHQmmY"
    "IPv2AQWOtdFCG3Sb72aT1/DyFkTQTCGSccqo4lLkGi3kLGkFVUrSdFJWmviR07EaOVYjx2"
    "rkQKsR8X29FaFXrEeyqqfMmOefzKepSXhYuYhbk/yKxPyA+hCwhbVPAVwo/hUpxuVsCGEo"
    "+t+vFs6Kj7VwFm18arFEz7DvbUPhO/YCHWN8yc3u+UkjL7nXzp0kwMYecovRpqL8ISJSnc"
    "bqny77u8aF2dOv6udnJ41cOZDwbZ3lEdo8CIDYiyqLc13zNFm/CzfNGA8fcZ7NLsfmDoux"
    "uXUpNjdTHjEeFjM0CPcUR5PIiwEbCpI9Ub8gTR9WdxRZotq10e+a/T8/1GKXr+RaN7viEW"
    "HnKxkal+N+1xDPAYiSwwFhu9TNK2mZIuxGN01V56O9w3y0t85HOz8f3Hf2LDOyymOZ8apl"
    "hhr8gVxi6BBge64V3GHELSdlVxgo9TmYCwyTsAr3FzjaM9dXezxhr3qcm8le3jTOW+9b7e"
    "a7Vlu4qJGsLO9LVn9yPbn9vuIeAnnErbI7rkle7nN++Ec1kRoVIMbuPyfA87OzHQAKr60A"
    "VVvuoEZVDbAJ8dPNoL/lnJZK8hsZtlntv5qLw42kPgygJfxkvJndKsFW7+n/5IleXA06+W"
    "1IvqDz2rfjy/8B91WLZA=="
)

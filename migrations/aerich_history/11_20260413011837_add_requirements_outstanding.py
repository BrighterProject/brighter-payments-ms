from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" ADD "requirements_outstanding" BOOL NOT NULL DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "owner_stripe_accounts" DROP COLUMN "requirements_outstanding";"""


MODELS_STATE = (
    "eJztmG1v2joUx78Kyism9VYtsA1N05VCSbdcFago3F3tbopMcgCriZ06zjq08d1nOwl5IC"
    "BCn5jGG0SOzz/2+dmOz/EPzaMOuMHp4J4Au+EM+6DbNg0J197VfmgEeSD+bPE6qWnI91Mf"
    "aeBo4ioZlf5WoAQWihTKA02EEdmykylyAxAmBwJb+HFMibCS0HWlkdpSTWapKST4LgSL0x"
    "nwOTDR8P9XYcbEge8QJI/+rTXF4Dq5KLAj+1Z2iy98ZRuPze6l8pTdTSybuqFHUm9/weeU"
    "rNzDEDunUiPbZiDCQxycTBhylHH4iSkasTBwFsJqqE5qcGCKQlfC0N5PQ2JLBjXVk/xp/a"
    "1VwGNTItFiCVrEvoyiSmNWVk12dfFRH9abb16pKGnAZ0w1KiLaUgkRR5FUcU1B2gxk2Bbi"
    "60C7ooVjD8qh5pUFuE4sPU3+7AM5MaSU0xWWYE7w7cdUEzE4A+Iu4hncwnhk9oybkd67lp"
    "F4QXDnKkT6yJAtDWVdFKz1aEqo2B/RLlq9pPbJHH2sycfa50HfKE7cym/0WZNjQiGnFqH3"
    "FnIyiy2xJmCEZzqx0Yattk+ymufdLQ+bxodsjZRY/uNWiu5ijlg5ulJxgaHwOUR6moe+Wy"
    "6QGZ+Lx8br11tw/qsPFVHhVVja/bipEbXl0dqC2wwCC4gMsgRsh1IXENnwpVlXF8hOhPyp"
    "vjBVT7Xd12ZnMLjKfU065qgAddzrGMP6uWItnDBXZrM/KgD+BgyLLqqSzcqOSPNIGdyFmI"
    "EHoleLhjzgiDhyWNUQb3vNEflyKVO86W0mN5GGCbJv7xFzrLUW2qCbfNebvIZXtCCCZgqR"
    "jFNGFefD12ghp0grSZWTpq35sR85HVPiY0p8TIkPNCUW39dbEXrFpDiveswd8/ST+TiJcR"
    "hUriQykj+RmM+oD4wvrH2qsFLxn0gxrqkCCALR/34FWV58LMjyaOOsxRI9w74lb+k79gId"
    "Y3zOw+7pSSMvuVwtZBJgYw+55WhTUTGJiFSnsfq32/1d48Ls6Vf187OTRqEcSPi2ztZuD0"
    "LGgNiLKoszq3mcXb8LN80YDx+Qz+aXY3OHxdjcuBSb61se8TAoZ2iQ0FMcTSLrUxtKNnui"
    "fkaaPqxK5TxR7drod83+h3e12OULudbNrnhE2PlChsbluN81xDMDUXI4IGyXunklLVOE4z"
    "ukqvPR3mE+2hvno12cj9B39iwz8spjmfGiZYYa/IFcYujAsD3XSu4w4paTbVcYKPU5mAsM"
    "k/AK9xc4OjOzqz2esBdN52ayl78a5623rXbzTastXNRIVpa3W1Z/cjG5+b7iGzCZ4lY5HT"
    "OS5/ucH36qJrZGBYix++8J8PzsbAeAwmsjQNVWSNSoqgHWIf5zM+hvyNNSSfEgwzav/ay5"
    "OFjb1IcBdAs/GW/utEqw1Xv6f0WiF1eDTvEYki/ovPTt+PIXTzQOAQ=="
)

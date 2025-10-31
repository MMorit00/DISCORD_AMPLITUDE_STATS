"""领域常量定义。"""


class AssetClass:
    """资产类别常量"""

    us_qdii = "US_QDII"
    csi300 = "CSI300"
    cgb_3_5y = "CGB_3_5Y"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.us_qdii, cls.csi300, cls.cgb_3_5y]


class FundType:
    """基金类型常量"""

    domestic = "domestic"
    qdii = "QDII"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.domestic, cls.qdii]



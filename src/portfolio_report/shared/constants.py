"""跨层共享的常量定义。"""


class TransactionFields:
    """`transactions.csv` 字段名常量。"""

    tx_id = "tx_id"
    date = "date"
    fund_code = "fund_code"
    amount = "amount"
    shares = "shares"
    type = "type"
    status = "status"
    confirm_date = "confirm_date"
    expected_nav_date = "expected_nav_date"
    expected_confirm_date = "expected_confirm_date"
    nav_kind = "nav_kind"
    created_at = "created_at"
    updated_at = "updated_at"

    @classmethod
    def all_fields(cls) -> list[str]:
        return [
            cls.tx_id,
            cls.date,
            cls.fund_code,
            cls.amount,
            cls.shares,
            cls.type,
            cls.status,
            cls.confirm_date,
            cls.expected_nav_date,
            cls.expected_confirm_date,
            cls.nav_kind,
            cls.created_at,
            cls.updated_at,
        ]


class Defaults:
    """项目默认配置。"""

    timezone = "Asia/Shanghai"
    cutoff_time = "15:00"
    cache_ttl = 300
    date_format = "%Y-%m-%d"
    datetime_format = "%Y-%m-%d %H:%M:%S"


class ThresholdKeys:
    """阈值配置键名。"""

    rebalance_light_absolute = "rebalance_light_absolute"
    rebalance_strong_relative = "rebalance_strong_relative"
    tactical_drawdown = "tactical_drawdown"
    tactical_profit = "tactical_profit"
    cooldown_days = "cooldown_days"


class CooldownKeys:
    """冷却期配置键名。"""

    light = "light"
    strong = "strong"
    tactical = "tactical"



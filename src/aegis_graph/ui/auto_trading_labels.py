"""Bilingual display labels for the Auto Trading REG surfaces.

Display-only translations live here so semantic IDs and accepted English definitions stay
unchanged and auditable.
"""

AUTO_TRADING_DISPLAY_LABELS = {
    "auto.cash.bot_sell_proceeds": "机器人归属卖出收入 · Bot-Owned SELL Proceeds",
    "auto.capital.flat": "资金归属已完成对账 · Capital Attribution Reconciled",
    "auto.cash.clob_free": "CLOB 物理可用现金 · Physical CLOB Free Cash",
    "auto.cash.manual_sell_proceeds": "手动归属卖出收入 · Manual-Owned SELL Proceeds",
    "auto.cash.orderable": "自动交易可下单现金 · Orderable Automatic Cash",
    "auto.cash.safety": "安全资金账本 · Safety Cash Ledger",
    "auto.cash.physical_sell_proceeds": "钱包实际卖出收入 · Physical Wallet SELL Proceeds",
    "auto.cash.trading": "自动策略交易现金 · Automatic Strategy Trading Cash",
    "auto.cash.unknown_sell_proceeds": "未归属卖出收入 · Unknown SELL Proceeds",
    "auto.order.already_submitted": "机器人订单已提交 · Bot Order Already Submitted",
    "auto.order.minimum": "最小可执行订单 · Minimum Executable Order",
    "auto.position.bot_same_round": "本轮已有机器人持仓 · Bot Position Exists For Same Round",
    "auto.position.bot_sold_shares": "混合卖出已消耗机器人份额 · Bot Shares Consumed By Mixed SELL",
    "auto.position.bot_total_shares": "混合卖出前机器人份额 · Bot Shares Before Mixed SELL",
    "auto.position.manual_exists": "存在手动持仓 · Manual Position Exists",
    "auto.position.manual_sell_shares": "手动归属卖出份额 · Manual-Owned SELL Shares",
    "auto.position.manual_total_shares": "混合卖出前手动份额 · Manual Shares Before Mixed SELL",
    "auto.position.physical_sell_shares": "钱包实际卖出份额 · Physical Wallet SELL Shares",
    "auto.position.unknown_sell_shares": "未归属卖出份额 · Unknown SELL Shares",
    "auto.settlement.expected_redeem_shares": "机器人仍预计赎回份额 · Bot Shares Still Expected To REDEEM",
    "auto.settlement.mixed_sell_verified": "混合卖出回执已验证 · Mixed SELL Receipt Verified",
    "auto.settlement.pending": "结算现金同步等待中 · Settlement Cash Sync Pending",
    "auto.signal.execution_decision": "自动信号执行决定 · Automatic Signal Execution Decision",
    "auto.rule.mixed_sell_partition": "物理卖出按手动/机器人/未知归属拆分 · Partition Physical SELL Ownership",
    "auto.rule.signal_execution_decision": "自动信号执行门槛 · Automatic Signal Execution Gate",
    "auto.inv.low_trading_cash_blocks_explicitly": "真实低交易现金必须明确阻止下单 · Explicit Low-Cash Block",
    "auto.inv.manual_position_never_vetoes_signal": "手动持仓不得否决可执行自动信号 · Manual Position Must Not Veto Auto Signal",
    "auto.inv.manual_sell_does_not_exceed_manual_ownership": "手动卖出归属不得超过手动持有份额 · Manual Sell Attribution ≤ Manual Ownership",
    "auto.inv.mixed_sell_cash_conservation": "混合卖出现金必须守恒 · Mixed SELL Cash Conservation",
    "auto.inv.mixed_sell_share_conservation": "混合卖出份额必须守恒 · Mixed SELL Share Conservation",
    "auto.inv.orderable_respects_cash": "自动可下单现金不得超过真实资金 · Orderable Cash Respects Available Cash",
    "auto.inv.sold_bot_shares_not_waiting_redeem": "已卖机器人份额不得继续等待赎回 · Sold Bot Shares Not Awaiting REDEEM",
    "auto.inv.verified_zero_redeem_not_stuck_pending": "已验证且零待赎回时不得卡在结算中 · Verified Zero-Redeem Not Stuck Pending",
}

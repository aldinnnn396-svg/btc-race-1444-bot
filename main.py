import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

closes = []
sum_close = 0
sum_sq_close = 0

mode = ""
entry_price = 0
entry_bar = 0
pending = False
pending_mode = ""

def on_batch(state, batch):
    global closes, sum_close, sum_sq_close
    global mode, entry_price, entry_bar, pending, pending_mode

    c = state.close(SYMBOL)
    if c is not None:
        closes.append(c)
        sum_close += c
        sum_sq_close += c * c
        if len(closes) > 240:
            old_c = closes[-241]
            sum_close -= old_c
            sum_sq_close -= old_c * old_c

    for fill in batch.get("fills", []):
        side = fill.get("side")
        status = fill.get("status")
        if side == "buy" and status == "filled":
            mode = pending_mode
            entry_price = int(float(fill["price"]))
            entry_bar = state.seq
            pending = False
        elif side == "buy" and status == "rejected":
            pending = False
            mode = ""
        elif side == "sell" and status == "filled":
            mode = ""
            entry_price = 0
            pending = False
    if state.seq < 250 or state.seq == 1439:
        return []

    pos = state.positions.get(SYMBOL)
    is_holding = pos is not None and getattr(pos, "qty", 0) > 0

    if is_holding:
        move_bps = ((c - entry_price) * 10000) // entry_price
        bars_held = state.seq - entry_bar
        if mode == "dip":
            if move_bps >= 80 or move_bps <= -60 or bars_held >= 180:
                return [{
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": pos.qty,
                    "max_slippage_bps": 300
                }]
        elif mode == "mr":
            if move_bps >= 120 or move_bps <= -100 or bars_held >= 480:
                return [{
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": pos.qty,
                    "max_slippage_bps": 300
                }]
        return []

    if pending:
        return []

    if state.seq >= 1380:
        return []

    ret_30 = ((closes[-1] - closes[-31]) * 10000) // closes[-31]
    ret_120 = ((closes[-1] - closes[-121]) * 10000) // closes[-121]
    in_downtrend = (ret_120 <= -80)

    prev_close = closes[-2]

    mean_240 = sum_close // 240
    var_240 = max(0, (sum_sq_close // 240) - (mean_240 * mean_240))
    std_240 = math.isqrt(var_240)

    if ret_30 <= -40 and c > prev_close:
        pending = True
        pending_mode = "dip"
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash // 2,
            "max_slippage_bps": 300
        }]

    return []

makefun_bars.run(on_batch)

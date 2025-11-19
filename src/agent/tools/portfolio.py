"""Portfolio monitoring and P&L tracking."""
from typing import Any, Dict
from claude_agent_sdk import tool
from pathlib import Path
import aiosqlite
import os

@tool(
    name="update_portfolio",
    description="Update portfolio position for a symbol",
    input_schema={
        "symbol": str,
        "position_type": str,
        "entry_price": float,
        "quantity": float,
        "stop_loss": float,
        "take_profit": float
    }
)
async def update_portfolio(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update or create portfolio position."""
    try:
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO portfolio_state
                (symbol, position_type, entry_price, quantity, stop_loss, take_profit, current_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    position_type=excluded.position_type,
                    entry_price=excluded.entry_price,
                    quantity=excluded.quantity,
                    stop_loss=excluded.stop_loss,
                    take_profit=excluded.take_profit,
                    current_price=excluded.current_price,
                    timestamp=CURRENT_TIMESTAMP
                """,
                (
                    args["symbol"],
                    args["position_type"],
                    args["entry_price"],
                    args["quantity"],
                    args.get("stop_loss", 0),
                    args.get("take_profit", 0),
                    args["entry_price"]  # Initial current_price
                )
            )
            await db.commit()

        return {
            "content": [{
                "type": "text",
                "text": f"Portfolio updated: {args['position_type']} position in {args['symbol']}"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error updating portfolio: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="calculate_pnl",
    description="Calculate P&L for current positions",
    input_schema={
        "symbol": str,
        "current_price": float
    }
)
async def calculate_pnl(args: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate unrealized P&L for a position."""
    try:
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))
        symbol = args["symbol"]
        current_price = args["current_price"]

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM portfolio_state WHERE symbol = ?",
                (symbol,)
            ) as cursor:
                row = await cursor.fetchone()

                if not row:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"No position found for {symbol}"
                        }]
                    }

                position = dict(row)
                entry_price = position['entry_price']
                quantity = position['quantity']
                position_type = position['position_type']

                if position_type == "NONE":
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"No active position for {symbol}"
                        }]
                    }

                # Calculate P&L
                if position_type == "LONG":
                    pnl = (current_price - entry_price) * quantity
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:  # SHORT
                    pnl = (entry_price - current_price) * quantity
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100

                # Update current price and PNL
                await db.execute(
                    """
                    UPDATE portfolio_state
                    SET current_price = ?, unrealized_pnl = ?
                    WHERE symbol = ?
                    """,
                    (current_price, pnl, symbol)
                )
                await db.commit()

                # Check stop loss / take profit
                alerts = []
                if position['stop_loss'] and position_type == "LONG" and current_price <= position['stop_loss']:
                    alerts.append(f"⚠️  STOP LOSS HIT at ${current_price}")
                if position['take_profit'] and position_type == "LONG" and current_price >= position['take_profit']:
                    alerts.append(f"🎯 TAKE PROFIT HIT at ${current_price}")

                pnl_text = f"""
📊 P&L Report for {symbol}

Position: {position_type}
Entry Price: ${entry_price:.2f}
Current Price: ${current_price:.2f}
Quantity: {quantity}

Unrealized P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)
Stop Loss: ${position['stop_loss']:.2f}
Take Profit: ${position['take_profit']:.2f}

{chr(10).join(alerts) if alerts else ''}
"""

                return {
                    "content": [{"type": "text", "text": pnl_text}],
                    "pnl": {
                        "unrealized_pnl": pnl,
                        "pnl_percentage": pnl_pct,
                        "alerts": alerts
                    }
                }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error calculating P&L: {str(e)}"}],
            "is_error": True
        }

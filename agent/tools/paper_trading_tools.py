"""Paper trading tools for Claude Agent SDK."""
from typing import Any, Dict
from claude_agent_sdk import tool
from pathlib import Path
import os

from agent.database.paper_schema import init_paper_trading_db
from agent.database.paper_operations import PaperTradingDatabase
from agent.paper_trading.portfolio_manager import PaperPortfolioManager
from agent.paper_trading.audit_dashboard import AuditDashboard

@tool(
    name="create_paper_portfolio",
    description="Create a new paper trading portfolio with specified configuration",
    input_schema={
        "name": str,
        "starting_capital": float,
        "execution_mode": str,  # instant, realistic, historical
        "max_position_size_pct": float,
        "max_total_exposure_pct": float,
        "max_daily_loss_pct": float,
        "max_drawdown_pct": float
    }
)
async def create_paper_portfolio(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new paper trading portfolio."""
    try:
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        # Initialize paper trading schema if needed
        await init_paper_trading_db(db_path)

        db = PaperTradingDatabase(db_path)

        portfolio_id = await db.create_portfolio(
            name=args["name"],
            starting_capital=args.get("starting_capital", 100000.0),
            execution_mode=args.get("execution_mode", "realistic"),
            max_position_size_pct=args.get("max_position_size_pct", 5.0),
            max_total_exposure_pct=args.get("max_total_exposure_pct", 80.0),
            max_daily_loss_pct=args.get("max_daily_loss_pct", 5.0),
            max_drawdown_pct=args.get("max_drawdown_pct", 10.0)
        )

        return {
            "content": [{
                "type": "text",
                "text": f"Created paper trading portfolio '{args['name']}' (ID: {portfolio_id}) with ${args.get('starting_capital', 100000):,.2f} starting capital"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error creating portfolio: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="execute_paper_trade",
    description="Execute a trading signal in paper trading mode",
    input_schema={
        "portfolio_name": str,
        "symbol": str,
        "signal": dict,
        "current_price": float,
        "market_data": dict
    }
)
async def execute_paper_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a paper trade based on signal."""
    try:
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        manager = PaperPortfolioManager(db_path, args["portfolio_name"])
        await manager.initialize()

        result = await manager.execute_signal(
            signal=args["signal"],
            current_price=args["current_price"],
            market_data=args.get("market_data")
        )

        if result['executed']:
            details = result['execution_details']
            text = f"""
Paper Trade Executed: {result['action']}

Symbol: {details['symbol']}
Entry Price: ${details['entry_price']:.2f}
Quantity: {details['quantity']:.4f}
Stop Loss: ${details['stop_loss']:.2f}
Take Profit: ${details['take_profit']:.2f}
Slippage: {details['slippage_pct']:.3f}%
Execution Time: {details['execution_time_ms']}ms

{result['reason']}
"""
        else:
            text = f"Trade Not Executed: {result['reason']}"
            if 'violations' in result:
                text += f"\n\nViolations:\n" + "\n".join(f"- {v}" for v in result['violations'])

        return {
            "content": [{"type": "text", "text": text}],
            "trade_result": result
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error executing paper trade: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="get_paper_portfolio_status",
    description="Get current status and audit of paper trading portfolio",
    input_schema={
        "portfolio_name": str
    }
)
async def get_paper_portfolio_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get paper portfolio status."""
    try:
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        manager = PaperPortfolioManager(db_path, args["portfolio_name"])
        await manager.initialize()

        summary = await manager.get_portfolio_summary()

        # Format summary
        portfolio = summary['portfolio']
        positions = summary['positions']
        risk = summary['risk']
        metrics = summary['metrics']

        text = f"""
PAPER TRADING PORTFOLIO: {portfolio['name']}

Equity & P&L:
- Current Equity: ${portfolio['current_equity']:,.2f}
- Starting Capital: ${portfolio['starting_capital']:,.2f}
- Total P&L: ${portfolio['total_pnl']:+,.2f} ({portfolio['total_pnl_pct']:+.2f}%)
- Peak Equity: ${portfolio['peak_equity']:,.2f}

Positions ({positions['count']} open):
- Total Exposure: ${positions['total_exposure']:,.2f} ({positions['exposure_pct']:.1f}%)
- Unrealized P&L: ${positions['total_unrealized_pnl']:+,.2f}

Risk Status:
- Drawdown: {risk['current_drawdown_pct']:.2f}% / {risk['max_drawdown_limit']:.2f}%
- Exposure: {risk['exposure_pct']:.1f}% / {risk['max_exposure_limit']:.1f}%
- Circuit Breaker: {'ACTIVE' if portfolio['circuit_breaker_active'] else 'READY'}

Performance:
- Win Rate: {metrics['win_rate']:.1%} ({metrics['winning_trades']}W / {metrics['losing_trades']}L)
- Profit Factor: {metrics['profit_factor']:.2f if metrics['profit_factor'] else 'N/A'}
- Max Drawdown: {metrics['max_drawdown_pct']:.2f}%
- Avg Slippage: {metrics['avg_slippage_pct']:.3f}%
"""

        return {
            "content": [{"type": "text", "text": text}],
            "portfolio_summary": summary
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error getting portfolio status: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="update_paper_positions",
    description="Update all paper trading positions with current market prices",
    input_schema={
        "portfolio_name": str,
        "current_prices": dict  # {"BTC/USDT": 91351.10, ...}
    }
)
async def update_paper_positions(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update paper positions with current prices."""
    try:
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        manager = PaperPortfolioManager(db_path, args["portfolio_name"])
        await manager.initialize()

        await manager.update_positions(args["current_prices"])

        return {
            "content": [{
                "type": "text",
                "text": f"Updated positions with current prices"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error updating positions: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="reset_circuit_breaker",
    description="Manually reset circuit breaker to resume trading",
    input_schema={
        "portfolio_name": str
    }
)
async def reset_circuit_breaker(args: Dict[str, Any]) -> Dict[str, Any]:
    """Reset circuit breaker."""
    try:
        db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

        manager = PaperPortfolioManager(db_path, args["portfolio_name"])
        await manager.initialize()

        await manager.risk_manager.reset_circuit_breaker()

        return {
            "content": [{
                "type": "text",
                "text": "Circuit breaker reset - trading resumed"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error resetting circuit breaker: {str(e)}"}],
            "is_error": True
        }

"""Real-time audit dashboard for paper trading."""
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from datetime import datetime

from agent.database.paper_operations import PaperTradingDatabase
from agent.paper_trading.metrics_calculator import PerformanceMetricsCalculator

class AuditDashboard:
    """Generate real-time paper trading audit reports."""

    def __init__(self, db: PaperTradingDatabase, portfolio_id: int):
        self.db = db
        self.portfolio_id = portfolio_id
        self.console = Console()
        self.metrics_calc = PerformanceMetricsCalculator(db, portfolio_id)

    async def display_dashboard(self) -> None:
        """Display comprehensive real-time dashboard."""
        portfolio = await self.db.get_portfolio(self.portfolio_id)
        positions = await self.db.get_open_positions(self.portfolio_id)
        metrics = await self.metrics_calc.calculate_metrics()
        violations = await self.db.get_risk_violations(self.portfolio_id, hours=24)

        # Clear screen and display
        self.console.clear()
        self.console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
        self.console.print(f"[bold cyan]PAPER TRADING PORTFOLIO AUDIT[/bold cyan]")
        self.console.print(f"[bold]Portfolio:[/bold] {portfolio['name']} | [bold]Mode:[/bold] {portfolio['execution_mode']}")
        self.console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")

        # Portfolio Overview
        self._display_portfolio_overview(portfolio, metrics)

        # Open Positions
        self._display_positions(positions)

        # Performance Metrics
        self._display_performance_metrics(metrics)

        # Risk Compliance
        self._display_risk_compliance(portfolio, positions, metrics, violations)

        # Recent Violations
        if violations:
            self._display_violations(violations)

    def _display_portfolio_overview(self, portfolio: Dict, metrics: Dict) -> None:
        """Display portfolio overview section."""
        starting = portfolio['starting_capital']
        current = portfolio['current_equity']
        total_pnl = current - starting
        total_pnl_pct = (total_pnl / starting) * 100

        pnl_color = "green" if total_pnl >= 0 else "red"

        table = Table(title="Portfolio Overview", show_header=False)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Starting Capital", f"${starting:,.2f}")
        table.add_row("Current Equity", f"${current:,.2f}")
        table.add_row(
            "Total P&L",
            f"[{pnl_color}]{total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)[/{pnl_color}]"
        )
        table.add_row("Realized P&L", f"${metrics['realized_pnl']:+,.2f}")
        table.add_row("Unrealized P&L", f"${metrics['unrealized_pnl']:+,.2f}")
        table.add_row("Peak Equity", f"${portfolio['peak_equity']:,.2f}")

        self.console.print(table)
        self.console.print()

    def _display_positions(self, positions: List[Dict]) -> None:
        """Display open positions."""
        if not positions:
            self.console.print("[yellow]No open positions[/yellow]\n")
            return

        table = Table(title=f"Open Positions ({len(positions)})")
        table.add_column("Symbol", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Entry", style="blue")
        table.add_column("Current", style="blue")
        table.add_column("Quantity")
        table.add_column("P&L", style="green")
        table.add_column("Stop Loss", style="red")
        table.add_column("Take Profit", style="green")

        for pos in positions:
            pnl = pos['unrealized_pnl']
            pnl_pct = (pnl / (pos['entry_price'] * pos['quantity'])) * 100
            pnl_color = "green" if pnl >= 0 else "red"

            table.add_row(
                pos['symbol'],
                pos['position_type'],
                f"${pos['entry_price']:.2f}",
                f"${pos['current_price']:.2f}",
                f"{pos['quantity']:.4f}",
                f"[{pnl_color}]{pnl:+,.2f} ({pnl_pct:+.2f}%)[/{pnl_color}]",
                f"${pos['stop_loss']:.2f}" if pos['stop_loss'] else "-",
                f"${pos['take_profit']:.2f}" if pos['take_profit'] else "-"
            )

        self.console.print(table)
        self.console.print()

    def _display_performance_metrics(self, metrics: Dict) -> None:
        """Display performance metrics."""
        table = Table(title="Performance Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Trades", str(metrics['total_trades']))
        table.add_row("Win Rate", f"{metrics['win_rate']:.1%}")
        table.add_row("Winning Trades", str(metrics['winning_trades']))
        table.add_row("Losing Trades", str(metrics['losing_trades']))
        table.add_row("Profit Factor", f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] else "N/A")

        if metrics['sharpe_ratio']:
            table.add_row("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
        if metrics['sortino_ratio']:
            table.add_row("Sortino Ratio", f"{metrics['sortino_ratio']:.2f}")

        table.add_row("Max Drawdown", f"{metrics['max_drawdown_pct']:.2f}%")
        table.add_row("Avg Win", f"${metrics['avg_win']:+,.2f}")
        table.add_row("Avg Loss", f"${metrics['avg_loss']:+,.2f}")
        table.add_row("Largest Win", f"${metrics['largest_win']:,.2f}")
        table.add_row("Largest Loss", f"${metrics['largest_loss']:,.2f}")

        self.console.print(table)
        self.console.print()

    def _display_risk_compliance(
        self,
        portfolio: Dict,
        positions: List[Dict],
        metrics: Dict,
        violations: List[Dict]
    ) -> None:
        """Display risk compliance status."""
        # Calculate current values
        total_exposure = sum(p['quantity'] * p['current_price'] for p in positions)
        exposure_pct = (total_exposure / portfolio['current_equity']) * 100 if portfolio['current_equity'] > 0 else 0

        current_dd = metrics['current_drawdown_pct']

        # Limits
        max_exposure = portfolio['max_total_exposure_pct']
        max_dd = portfolio['max_drawdown_pct']
        circuit_breaker = portfolio['circuit_breaker_active']

        table = Table(title="Risk Compliance")
        table.add_column("Rule", style="cyan")
        table.add_column("Current", style="white")
        table.add_column("Limit", style="yellow")
        table.add_column("Status", style="white")

        # Exposure
        exposure_status = "✓" if exposure_pct <= max_exposure else "✗"
        exposure_color = "green" if exposure_pct <= max_exposure else "red"
        table.add_row(
            "Total Exposure",
            f"{exposure_pct:.1f}%",
            f"{max_exposure:.1f}%",
            f"[{exposure_color}]{exposure_status}[/{exposure_color}]"
        )

        # Drawdown
        dd_status = "✓" if current_dd <= max_dd else "✗"
        dd_color = "green" if current_dd <= max_dd else "red"
        table.add_row(
            "Drawdown",
            f"{current_dd:.2f}%",
            f"{max_dd:.2f}%",
            f"[{dd_color}]{dd_status}[/{dd_color}]"
        )

        # Circuit breaker
        cb_status = "ACTIVE" if circuit_breaker else "READY"
        cb_color = "red" if circuit_breaker else "green"
        table.add_row(
            "Circuit Breaker",
            f"[{cb_color}]{cb_status}[/{cb_color}]",
            "-",
            f"[{cb_color}]{'✗' if circuit_breaker else '✓'}[/{cb_color}]"
        )

        # Violations count
        critical_violations = len([v for v in violations if v['severity'] == 'CRITICAL'])
        violation_color = "red" if critical_violations > 0 else "green"
        table.add_row(
            "Violations (24h)",
            f"[{violation_color}]{len(violations)} ({critical_violations} critical)[/{violation_color}]",
            "-",
            f"[{violation_color}]{'✗' if critical_violations > 0 else '✓'}[/{violation_color}]"
        )

        self.console.print(table)
        self.console.print()

    def _display_violations(self, violations: List[Dict]) -> None:
        """Display recent violations."""
        table = Table(title="Recent Violations (Last 24h)", show_lines=True)
        table.add_column("Time", style="cyan")
        table.add_column("Severity")
        table.add_column("Type")
        table.add_column("Message")

        for v in violations[:10]:  # Show last 10
            severity = v['severity']
            color = {
                'CRITICAL': 'red',
                'WARNING': 'yellow',
                'INFO': 'blue'
            }.get(severity, 'white')

            table.add_row(
                str(v['triggered_at'])[:19],
                f"[{color}]{severity}[/{color}]",
                v['rule_type'],
                v['message'] or ""
            )

        self.console.print(table)
        self.console.print()

    async def display_execution_quality(self, limit: int = 20) -> None:
        """Display execution quality analysis."""
        trades = await self.db.get_trade_history(self.portfolio_id, limit=limit)

        table = Table(title=f"Execution Quality (Last {limit} Trades)")
        table.add_column("Time", style="cyan")
        table.add_column("Symbol")
        table.add_column("Type")
        table.add_column("Signal $", style="blue")
        table.add_column("Fill $", style="blue")
        table.add_column("Slippage %")
        table.add_column("Mode")

        for trade in trades:
            slippage = trade['slippage_pct']
            slip_color = "green" if slippage < 0.1 else "yellow" if slippage < 0.3 else "red"

            table.add_row(
                str(trade['executed_at'])[:19],
                trade['symbol'],
                trade['trade_type'],
                f"${trade['signal_price']:.2f}" if trade['signal_price'] else "-",
                f"${trade['actual_fill_price']:.2f}",
                f"[{slip_color}]{slippage:.3f}%[/{slip_color}]",
                trade['execution_mode']
            )

        self.console.print(table)

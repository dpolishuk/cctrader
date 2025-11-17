"""Market sentiment analysis using Perplexity."""
from typing import Any, Dict
from claude_agent_sdk import tool

# Note: Perplexity will be accessed via MCP in the agent configuration
# These tools coordinate Perplexity queries

@tool(
    name="analyze_market_sentiment",
    description="Analyze market sentiment for a crypto symbol using news and social media",
    input_schema={
        "symbol": str,
        "context": str
    }
)
async def analyze_market_sentiment(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query Perplexity for market sentiment analysis.

    Note: This tool provides a structured query that the agent will use
    with the Perplexity MCP tool.
    """
    symbol = args.get("symbol", "BTC")
    context = args.get("context", "")

    # Create structured query for Perplexity
    query = f"""Analyze the current market sentiment for {symbol} cryptocurrency.
Include:
1. Recent major news events (last 24-48 hours)
2. Overall market sentiment (bullish/bearish/neutral)
3. Key factors influencing price
4. Any significant regulatory or technical developments
{f'Context: {context}' if context else ''}

Provide a concise summary with sentiment score if possible."""

    return {
        "content": [{
            "type": "text",
            "text": f"Query Perplexity with: {query}\n\n"
                    "The agent will use mcp__perplexity-mcp__perplexity_ask to get results."
        }],
        "perplexity_query": query,
        "symbol": symbol
    }

@tool(
    name="detect_market_events",
    description="Detect significant market events that could impact crypto prices",
    input_schema={
        "symbols": list,
        "lookback_hours": int
    }
)
async def detect_market_events(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use Perplexity to detect significant events affecting crypto markets.
    """
    symbols = args.get("symbols", ["BTC", "ETH"])
    lookback = args.get("lookback_hours", 24)

    query = f"""Identify any significant events in the last {lookback} hours affecting {', '.join(symbols)}
and the broader cryptocurrency market. Include:
1. Exchange hacks or security incidents
2. Regulatory announcements
3. Major partnerships or integrations
4. Significant whale movements or on-chain activity
5. Macro economic events affecting crypto

Prioritize events by potential price impact."""

    return {
        "content": [{
            "type": "text",
            "text": f"Event detection query for Perplexity: {query}"
        }],
        "perplexity_query": query
    }

"""Wrapper for Claude Agent to provide scanner-compatible interface."""
from typing import Dict, Any, Optional
import asyncio
import logging
import time
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock
)
from .tools import set_signal_queue, clear_signal_queue

logger = logging.getLogger(__name__)

class AgentWrapper:
    """Wraps Claude Agent SDK to provide scanner-compatible interface."""

    def __init__(
        self,
        agent_options: ClaudeAgentOptions,
        token_tracker: Optional[Any] = None,
        session_manager: Optional[Any] = None,
        operation_type: str = "scanner"
    ):
        """
        Initialize wrapper.

        Args:
            agent_options: ClaudeAgentOptions with tools, system prompt, etc.
            token_tracker: Optional TokenTracker instance for tracking usage
            session_manager: Optional SessionManager for session persistence
            operation_type: Type of operation for session isolation (default: scanner)
        """
        self.agent_options = agent_options
        self.token_tracker = token_tracker
        self.session_manager = session_manager
        self.operation_type = operation_type

    async def run(self, prompt: str, symbol: str = None) -> Dict[str, Any]:
        """
        Run analysis and return structured response.

        Uses Claude Agent SDK with tool-based output pattern:
        1. Creates signal queue for communication
        2. Sets queue in context for submit_trading_signal tool
        3. Sends prompt to agent via ClaudeSDKClient
        4. Waits for agent to call submit_trading_signal (max 45s)
        5. Returns signal dict or confidence=0 on timeout/error

        Args:
            prompt: Analysis prompt
            symbol: Optional symbol for metadata tracking

        Returns:
            Dict with confidence, entry_price, stop_loss, tp1, scoring components, analysis
        """
        # Create queue for signal communication
        signal_queue = asyncio.Queue()

        # Set queue in module-level storage so submit_trading_signal tool can access it
        set_signal_queue(signal_queue)

        # Track timing for token tracking
        start_time = time.time()
        final_message = None

        try:
            # Get existing session ID if session manager is available
            session_id = None
            if self.session_manager:
                session_id = await self.session_manager.get_session_id(self.operation_type)
                if session_id:
                    logger.info(f"Resuming {self.operation_type} session: {session_id}")
                else:
                    logger.info(f"Starting new {self.operation_type} session")

            # Create agent client with configured options
            async with ClaudeSDKClient(options=self.agent_options) as client:
                logger.info("Starting agent analysis")

                # Send analysis prompt (with session resumption if available)
                query_options = {}
                if session_id:
                    query_options['resume'] = session_id

                await client.query(prompt, **query_options)

                # Process agent messages (log for debugging and capture final message)
                message_task = asyncio.create_task(
                    self._process_messages(client)
                )

                # Wait for signal with 120-second timeout
                # (Increased from 45s to accommodate Claude's processing speed with bundled tools)
                try:
                    signal = await asyncio.wait_for(
                        signal_queue.get(),
                        timeout=120.0
                    )

                    logger.info(
                        f"Agent analysis complete: confidence={signal['confidence']}, "
                        f"symbol={signal['symbol']}"
                    )

                    # Cancel message processing task
                    message_task.cancel()
                    try:
                        await message_task
                    except asyncio.CancelledError:
                        pass

                    # Record token usage if tracker is available
                    if self.token_tracker and hasattr(self, '_result_message'):
                        duration = time.time() - start_time
                        await self.token_tracker.record_usage(
                            result=self._result_message,
                            operation_type="mover_analysis",
                            duration_seconds=duration,
                            metadata={"symbol": symbol or signal.get('symbol', 'unknown')}
                        )

                    # Save session ID if session manager is available and this was a new session
                    if self.session_manager and hasattr(client, 'session_id') and client.session_id:
                        await self.session_manager.save_session_id(
                            self.operation_type,
                            client.session_id,
                            metadata=f'{{"symbol": "{symbol or signal.get("symbol", "unknown")}"}}'
                        )

                    return signal

                except asyncio.TimeoutError:
                    logger.warning(
                        "Agent analysis timeout after 120 seconds - "
                        "agent did not call submit_trading_signal"
                    )

                    # Cancel message processing
                    message_task.cancel()
                    try:
                        await message_task
                    except asyncio.CancelledError:
                        pass

                    return self._timeout_response()

        except Exception as e:
            logger.error(f"Error in agent analysis: {e}", exc_info=True)
            return self._error_response(str(e))

        finally:
            # Clear module-level queue
            clear_signal_queue()

    async def _process_messages(self, client: ClaudeSDKClient):
        """
        Process messages from agent for logging/debugging.

        Args:
            client: ClaudeSDKClient instance
        """
        # Track tool calls to detect duplicates
        tool_call_count = {}
        message_count = 0

        # Track sentiment data for summary
        self._sentiment_findings = []

        try:
            async for message in client.receive_response():
                # Log raw message type for debugging
                message_type = type(message).__name__
                logger.debug(f"📬 Received message type: {message_type}")

                # Capture ResultMessage for token tracking
                if isinstance(message, ResultMessage):
                    self._result_message = message

                if isinstance(message, AssistantMessage):
                    # Track assistant messages for debugging
                    message_count += 1

                    # Count tools in this message
                    tools_in_message = []
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            tools_in_message.append(block.name)

                    # Log message summary
                    if tools_in_message:
                        logger.info(
                            f"📨 Message #{message_count}: {len(tools_in_message)} tool(s) - "
                            f"{', '.join(tools_in_message)}"
                        )
                    else:
                        logger.info(f"📨 Message #{message_count}: text only (no tools)")

                    # Process blocks for detailed logging
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Log full agent reasoning
                            text = block.text
                            if len(text) > 500:
                                logger.info(f"💭 Agent reasoning:\n{text[:500]}...\n[{len(text)-500} more chars]")
                            else:
                                logger.info(f"💭 Agent reasoning:\n{text}")
                        elif isinstance(block, ToolUseBlock):
                            # Track tool call frequency
                            tool_key = f"{block.name}"
                            tool_call_count[tool_key] = tool_call_count.get(tool_key, 0) + 1

                            # Log tool usage with full parameters
                            params_str = ""
                            if hasattr(block, 'input') and block.input:
                                import json
                                params_str = json.dumps(block.input, indent=2)

                            # Warn on duplicate calls
                            duplicate_marker = ""
                            if tool_call_count[tool_key] > 1:
                                duplicate_marker = f" ⚠️  DUPLICATE #{tool_call_count[tool_key]}"

                            logger.info(
                                f"🔧 Tool call: {block.name}{duplicate_marker}\n"
                                f"   Parameters: {params_str}"
                            )
                        elif isinstance(block, ToolResultBlock):
                            # Log tool results
                            tool_id = block.tool_use_id
                            is_error = block.is_error if hasattr(block, 'is_error') else False
                            content = block.content if hasattr(block, 'content') else str(block)

                            if is_error:
                                logger.error(f"❌ Tool error (ID: {tool_id}):\n{content}")
                            else:
                                # Check if this is a sentiment data result
                                self._process_sentiment_result(block)

                                # Truncate long results
                                content_str = str(content)
                                if len(content_str) > 300:
                                    logger.info(f"✅ Tool result (ID: {tool_id}):\n{content_str[:300]}...\n[{len(content_str)-300} more chars]")
                                else:
                                    logger.info(f"✅ Tool result (ID: {tool_id}):\n{content_str}")
                        else:
                            # Log unknown block types
                            logger.debug(f"🔍 Unknown block type: {type(block).__name__}")

                else:
                    # Log all non-AssistantMessage types for debugging
                    logger.debug(f"📦 Non-assistant message: {message_type}")
                    if hasattr(message, '__dict__'):
                        logger.debug(f"   Content: {message.__dict__}")

            # Log summary at end
            if tool_call_count:
                logger.info(
                    f"📊 Tool call summary: {sum(tool_call_count.values())} total calls, "
                    f"{len(tool_call_count)} unique tools"
                )
                for tool, count in sorted(tool_call_count.items(), key=lambda x: -x[1]):
                    if count > 1:
                        logger.warning(f"   ⚠️  {tool}: {count} calls (duplicates detected)")
                    else:
                        logger.info(f"   ✓ {tool}: {count} call")

        except asyncio.CancelledError:
            # Expected when analysis completes or times out
            pass
        except Exception as e:
            logger.error(f"Error processing agent messages: {e}", exc_info=True)

    def _timeout_response(self) -> Dict[str, Any]:
        """
        Build response for timeout case.

        Returns:
            Dict with confidence=0 and timeout message
        """
        return {
            'confidence': 0,
            'entry_price': None,
            'stop_loss': None,
            'tp1': None,
            'technical_score': 0.0,
            'sentiment_score': 0.0,
            'liquidity_score': 0.0,
            'correlation_score': 0.0,
            'analysis': 'Analysis timeout - exceeded 60 second limit'
        }

    def _error_response(self, error_msg: str) -> Dict[str, Any]:
        """
        Build response for error case.

        Args:
            error_msg: Error message to include

        Returns:
            Dict with confidence=0 and error message
        """
        return {
            'confidence': 0,
            'entry_price': None,
            'stop_loss': None,
            'tp1': None,
            'technical_score': 0.0,
            'sentiment_score': 0.0,
            'liquidity_score': 0.0,
            'correlation_score': 0.0,
            'analysis': f'Analysis error: {error_msg}'
        }

    def _process_sentiment_result(self, tool_result_block: ToolResultBlock):
        """
        Process sentiment tool result and display web search findings.

        Args:
            tool_result_block: ToolResultBlock from fetch_sentiment_data
        """
        try:
            import json

            # Extract content from block
            content = tool_result_block.content if hasattr(tool_result_block, 'content') else str(tool_result_block)

            # Try to parse as JSON
            if isinstance(content, str):
                # Check if this looks like a sentiment data result
                if 'sentiment_summary' not in content:
                    return

                data = json.loads(content)
            elif isinstance(content, list) and len(content) > 0:
                # Content might be a list with text block
                text_content = content[0].get('text', '') if isinstance(content[0], dict) else str(content[0])
                if 'sentiment_summary' not in text_content:
                    return
                data = json.loads(text_content)
            else:
                return

            # Extract key information
            web_results = data.get('web_results', [])
            sentiment_summary = data.get('sentiment_summary', '')
            warnings = data.get('warnings', [])
            success = data.get('success', False)

            # Display real-time sentiment findings
            logger.info("📰 Web Search:")

            if not success and warnings:
                # Failed web search
                logger.warning(f"   ⚠️  Web search failed - sentiment score defaulted")
                for warning in warnings:
                    logger.warning(f"      {warning}")
            elif not web_results or sentiment_summary == "No web results available for sentiment analysis":
                # No results found
                logger.info("   • No significant news found")
            else:
                # Extract 2-3 key bullet points from web results
                bullet_points = []
                for i, result in enumerate(web_results[:3]):  # Limit to top 3
                    title = result.get('title', '')
                    snippet = result.get('snippet', '')

                    # Create concise bullet point
                    if title:
                        bullet_points.append(f"• {title[:80]}{'...' if len(title) > 80 else ''}")
                    elif snippet:
                        bullet_points.append(f"• {snippet[:80]}{'...' if len(snippet) > 80 else ''}")

                # Display bullet points
                if bullet_points:
                    for point in bullet_points:
                        logger.info(f"   {point}")
                else:
                    logger.info("   • No significant news found")

            # Store for summary display later
            if hasattr(self, '_sentiment_findings'):
                self._sentiment_findings.append({
                    'success': success,
                    'warnings': warnings,
                    'web_results': web_results,
                    'summary': sentiment_summary,
                    'bullet_points': bullet_points if 'bullet_points' in locals() else []
                })

        except Exception as e:
            logger.debug(f"Could not process sentiment result: {e}")

    def get_sentiment_findings(self) -> list:
        """Get collected sentiment findings for summary display."""
        return getattr(self, '_sentiment_findings', [])

"""Wrapper for Claude Agent to provide scanner-compatible interface."""
from typing import Dict, Any
import asyncio
import logging
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock
)
from .tools import set_signal_queue, clear_signal_queue

logger = logging.getLogger(__name__)

class AgentWrapper:
    """Wraps Claude Agent SDK to provide scanner-compatible interface."""

    def __init__(self, agent_options: ClaudeAgentOptions):
        """
        Initialize wrapper.

        Args:
            agent_options: ClaudeAgentOptions with tools, system prompt, etc.
        """
        self.agent_options = agent_options

    async def run(self, prompt: str) -> Dict[str, Any]:
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

        Returns:
            Dict with confidence, entry_price, stop_loss, tp1, scoring components, analysis
        """
        # Create queue for signal communication
        signal_queue = asyncio.Queue()

        # Set queue in module-level storage so submit_trading_signal tool can access it
        set_signal_queue(signal_queue)

        try:
            # Create agent client with configured options
            async with ClaudeSDKClient(options=self.agent_options) as client:
                logger.info("Starting agent analysis")

                # Send analysis prompt
                await client.query(prompt)

                # Process agent messages (log for debugging)
                message_task = asyncio.create_task(
                    self._process_messages(client)
                )

                # Wait for signal with 45-second timeout
                try:
                    signal = await asyncio.wait_for(
                        signal_queue.get(),
                        timeout=45.0
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

                    return signal

                except asyncio.TimeoutError:
                    logger.warning(
                        "Agent analysis timeout after 45 seconds - "
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

        try:
            async for message in client.receive_response():
                # Log raw message type for debugging
                message_type = type(message).__name__
                logger.debug(f"📬 Received message type: {message_type}")

                if isinstance(message, AssistantMessage):
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
                    logger.info(f"📦 Non-assistant message: {message_type}")
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
            'analysis': 'Analysis timeout - exceeded 45 second limit'
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

"""
agents/nodes/research_agent.py
================================
Node 2 — Research Agent.

Implements a ReAct (Reason + Act) tool-calling loop using the LangChain
``ChatLiteLLM`` model bound to all portfolio tools.  The agent iterates
until the model produces a plain-text response with no further tool calls,
then writes the result as ``draft_answer``.

Why a manual loop instead of ``create_react_agent``?
-----------------------------------------------------
Using LangGraph's prebuilt ``create_react_agent`` as a subgraph would
require state-schema bridging between the inner MessagesState and our outer
AgentState, and would complicate the tool-log capture needed by the critique
agent.  A manual loop gives us identical behaviour with full control over
the ``tool_log`` structure.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from loguru import logger

from src.agents.prompts.loader import load_prompt
from src.agents.state import AgentState
from src.services.llm.service import LLMService

_MAX_TOOL_ITERATIONS = 10  # hard cap to prevent infinite loops


def research_agent_node(state: AgentState) -> dict[str, Any]:
    """
    Node 2 — Research Agent.

    Runs a ReAct loop:
    1. Send system prompt + query (+ prior critique if this is a revision) to
       the LLM model with all tools bound.
    2. If the model calls tools, execute them and loop.
    3. When the model stops calling tools, extract the text as ``draft_answer``.
    """
    query: str = state.get("query", "")
    critique: str | None = state.get("critique")
    tools_by_name: dict[str, Any] = state["_tools"]
    llm: LLMService = state["_llm"]

    tools_list = list(tools_by_name.values())
    model_with_tools = llm.chat_model.bind_tools(tools_list).with_retry(
        stop_after_attempt=4,
        wait_exponential_jitter=True,
    )

    system_prompt = load_prompt("research_agent")
    
    # Initialize from history
    initial_messages: list[Any] = list(state.get("messages", []))
    messages: list[Any] = list(initial_messages)
    
    # Ensure system message is at the start
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=system_prompt))
    
    # Add user query if it's the start of the turn (revision_count == 0)
    user_content = query
    if critique:
        user_content = (
            f"{query}\n\n"
            f"[Previous answer was rejected. Critique feedback:]\n{critique}"
        )

    messages.append(HumanMessage(content=user_content))
    tool_log: list[dict[str, Any]] = []
    steps: list[dict] = list(state.get("steps", []))

    for iteration in range(_MAX_TOOL_ITERATIONS):
        logger.debug("Research agent iteration {}", iteration + 1)

        response: AIMessage = model_with_tools.invoke(messages)
        messages.append(response)

        # No tool calls → the model has produced its final answer
        if not response.tool_calls:
            draft = response.content
            if isinstance(draft, list):
                # Some providers return content as a list of blocks
                draft = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in draft
                ).strip()
            logger.info(
                "Research agent finished after {} iteration(s) | draft_length={}",
                iteration + 1,
                len(str(draft)),
            )
            
            # Return new messages for the add_messages reducer
            # We skip the messages that were already in the state
            # but we include EVERYTHING added during this node call.
            # However, if we added a SystemMessage at the start, we should be careful.
            # LangGraph state management usually handles this.
            new_messages = messages[len(initial_messages):]
            
            return {
                "draft_answer": str(draft),
                "tool_log": tool_log,
                "messages": new_messages,
                "steps": steps,
            }

        # Execute each tool call
        for tool_call in response.tool_calls:
            tool_name: str = tool_call["name"]
            tool_args: dict = tool_call["args"]
            tool_id: str = tool_call["id"]

            logger.info("ResearchAgent: LLM requested tool '{}' with args={}", tool_name, tool_args)

            tool = tools_by_name.get(tool_name)
            if tool is None:
                tool_result = {"error": f"Unknown tool '{tool_name}'"}
                logger.warning("ResearchAgent: Unknown tool '{}' requested", tool_name)
            else:
                try:
                    tool_result = tool.invoke(tool_args)
                    logger.debug("ResearchAgent: Tool '{}' completed successfully", tool_name)
                except Exception as exc:
                    tool_result = {"error": str(exc)}
                    logger.error(
                        "ResearchAgent: tool '{}' raised an exception — {}", tool_name, exc
                    )

            tool_log.append({
                "tool_name": tool_name,
                "args": tool_args,
                "result": tool_result,
            })

            steps.append({
                "node": "ResearchAgent",
                "type": "tool",
                "message": tool_name,
                "data": {"args": tool_args, "result": tool_result},
            })

            messages.append(
                ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_id,
                )
            )

    # Iteration cap reached — extract best available content from last response
    logger.warning(
        "Research agent: reached max iterations ({}) — using last model response",
        _MAX_TOOL_ITERATIONS,
    )
    last = messages[-1] if messages else None
    draft = ""
    if isinstance(last, AIMessage) and last.content:
        draft = str(last.content)
    elif tool_log:
        draft = (
            "I retrieved the following data but was unable to synthesise a final answer. "
            "Here is the raw result: " + str(tool_log[-1].get("result", ""))
        )

    new_messages = messages[len(initial_messages):]
    return {
        "draft_answer": draft,
        "tool_log": tool_log,
        "messages": new_messages,
        "steps": steps,
    }

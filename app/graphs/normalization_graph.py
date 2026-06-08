from __future__ import annotations

from typing import TypedDict

from app.core.exceptions import BulkUpdateAPIError
from app.services.normalizer import ai_normalize, deterministic_normalize
from app.schemas import BulkUpdateItem, ParsedFile


class BulkUpdateGraphState(TypedDict, total=False):
    parsed_files: list[ParsedFile]
    marketplace: str
    use_ai: bool
    fallback_items: list[BulkUpdateItem]
    ai_items: list[BulkUpdateItem]
    items: list[BulkUpdateItem]
    result: list[BulkUpdateItem]
    ai_error: str


def build_bulk_update_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(BulkUpdateGraphState)

    async def deterministic_node(state: BulkUpdateGraphState) -> BulkUpdateGraphState:
        fallback_items = deterministic_normalize(state["parsed_files"], state["marketplace"])
        return {**state, "fallback_items": fallback_items}

    async def ai_node(state: BulkUpdateGraphState) -> BulkUpdateGraphState:
        if not state.get("use_ai", True):
            return state

        try:
            ai_items = await ai_normalize(
                state["parsed_files"],
                state["marketplace"],
                state.get("fallback_items", []),
            )
        except Exception as exc:
            return {**state, "ai_error": str(exc)}

        return {**state, "ai_items": ai_items}

    async def finalize_node(state: BulkUpdateGraphState) -> BulkUpdateGraphState:
        items = state.get("ai_items") or state.get("fallback_items") or []

        if state.get("ai_error"):
            for item in items:
                if "AI normalization failed; deterministic normalization was used." not in item.warnings:
                    item.warnings.append("AI normalization failed; deterministic normalization was used.")
                if item.status == "new":
                    item.status = "needs_review"

        return {**state, "items": items, "result": items}

    graph.add_node("deterministic_normalize", deterministic_node)
    graph.add_node("ai_normalize", ai_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "deterministic_normalize")
    graph.add_edge("deterministic_normalize", "ai_normalize")
    graph.add_edge("ai_normalize", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


async def run_bulk_update_graph(
    parsed_files: list[ParsedFile],
    *,
    marketplace: str,
    use_ai: bool,
) -> list[BulkUpdateItem]:
    try:
        graph = build_bulk_update_graph()
        state = await graph.ainvoke(
            {
                "parsed_files": parsed_files,
                "marketplace": marketplace,
                "use_ai": use_ai,
            }
        )
    except Exception as exc:
        raise BulkUpdateAPIError(
            "Bulk update LangGraph execution failed.",
            code="langgraph_execution_failed",
            status_code=500,
        ) from exc

    result = state.get("result")
    if result is None:
        raise BulkUpdateAPIError(
            "Bulk update LangGraph finished without a result.",
            code="missing_bulk_update_result",
            status_code=500,
        )

    return result

from langgraph.graph import StateGraph, START, END
from app.graph.state import TripState
from app.graph.nodes import (
    load_session,
    parse_intent,
    parse_request,
    chat_reply,
    parse_modification,
    search_hotels,
    rag_retrieve,
    enrich_coordinates,
    allocate_budget,
    generate_plan,
    modify_plan,
    validate_plan,
    optimize_route,
    auto_fix_plan,
    generate_answer,
)


def route_by_intent(state: TripState) -> str:
    intent = state.get("intent", "chat")
    if intent == "plan":
        return "plan"
    elif intent == "modify":
        return "modify"
    return "chat"


def route_after_budget(state: TripState) -> str:
    intent = state.get("intent", "plan")
    if intent == "modify":
        return "modify"
    return "generate"


def route_after_validate(state: TripState) -> str:
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)
    intent = state.get("intent", "plan")
    
    # 如果只有 warning（开放时间提示），不算严重错误，直接通过
    # 严格来说，超过预算才算严重错误
    critical_errors = [e for e in errors if "超过预算" in e or "重复景点" in e]
    
    if not critical_errors:
        return "pass"
    if retry_count < 2:
        return "retry_modify" if intent == "modify" else "retry_generate"
    return "force_fix"


def build_graph():
    """构建 LangGraph"""
    graph = StateGraph(TripState)
    
    # 节点
    graph.add_node("load_session", load_session)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("parse_request", parse_request)
    graph.add_node("chat_reply", chat_reply)
    graph.add_node("parse_modification", parse_modification)
    graph.add_node("rag_retrieve", rag_retrieve)
    graph.add_node("enrich_coordinates", enrich_coordinates)   # ⭐ 新增
    graph.add_node("search_hotels", search_hotels)
    graph.add_node("allocate_budget", allocate_budget)
    graph.add_node("generate_plan", generate_plan)
    graph.add_node("modify_plan", modify_plan)
    graph.add_node("validate_plan", validate_plan)
    graph.add_node("optimize_route", optimize_route)           # ⭐ 新增
    graph.add_node("auto_fix_plan", auto_fix_plan)
    graph.add_node("generate_answer", generate_answer)
    
    # START → 加载会话 → 解析意图
    graph.add_edge(START, "load_session")
    graph.add_edge("load_session", "parse_intent")
    
    # 意图分支
    graph.add_conditional_edges(
        "parse_intent",
        route_by_intent,
        {
            "plan": "parse_request",
            "modify": "parse_modification",
            "chat": "chat_reply",
        }
    )
    
    # 闲聊分支：生成一句回复后结束
    graph.add_edge("chat_reply", END)
    
    # 检索流程
    graph.add_edge("parse_request", "rag_retrieve")
    graph.add_edge("parse_modification", "rag_retrieve")
    graph.add_edge("rag_retrieve", "enrich_coordinates")   # ⭐ 补坐标
    graph.add_edge("enrich_coordinates", "search_hotels")
    graph.add_edge("search_hotels", "allocate_budget")
    
    # 预算后分支
    graph.add_conditional_edges(
        "allocate_budget",
        route_after_budget,
        {
            "generate": "generate_plan",
            "modify": "modify_plan",
        }
    )
    
    # 都进入校验
    graph.add_edge("generate_plan", "validate_plan")
    graph.add_edge("modify_plan", "validate_plan")
    
    # 校验分支
    graph.add_conditional_edges(
        "validate_plan",
        route_after_validate,
        {
            "retry_generate": "generate_plan",
            "retry_modify": "modify_plan",
            "force_fix": "auto_fix_plan",
            "pass": "optimize_route",   # ⭐ 通过后做路线优化
        }
    )
    
    # 兜底后也做路线优化
    graph.add_edge("auto_fix_plan", "optimize_route")
    graph.add_edge("optimize_route", "generate_answer")
    graph.add_edge("generate_answer", END)
    
    return graph.compile()


app_graph = build_graph()

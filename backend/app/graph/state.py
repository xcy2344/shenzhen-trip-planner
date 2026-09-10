from typing import TypedDict, List, Optional, Annotated
from operator import add


def _plan_reducer(current, new):
    """plan 键的合并器：多个节点写入时，用最新值"""
    return new


class TripRequest(TypedDict):
    """用户请求参数"""
    departure: str
    start_date: str
    end_date: str
    days: int
    people: int
    budget: float
    transport: str
    interests: List[str]
    preferences: str


class Attraction(TypedDict):
    """景点信息"""
    name: str
    location: str
    duration: float
    ticket: float
    open_time: str
    score: float
    description: str


class Restaurant(TypedDict):
    """餐饮信息"""
    name: str
    location: str
    avg_price: float
    cuisine: str
    score: float


class Hotel(TypedDict):
    """酒店信息"""
    name: str
    location: str
    price: float
    score: float
    distance: str


class DayPlan(TypedDict):
    """一天的行程"""
    day: int
    theme: str
    attractions: List[Attraction]
    restaurants: List[Restaurant]
    hotel: Optional[Hotel]
    transport: str
    total_duration: float
    estimated_cost: float


class TripState(TypedDict):
    """LangGraph 全局状态"""
    
    # ============ 会话 ============
    session_id: str
    
    # ============ 输入 ============
    user_input: str
    request: TripRequest
    
    # ============ 中间过程 ============
    intent: str
    prev_plan: List[DayPlan]
    modify_target: dict
    attractions: List[Attraction]
    restaurants: List[Restaurant]
    hotels: List[Hotel]
    weather: str
    route_info: dict
    
    # ============ 输出（加 reducer 处理并发写入）============
    plan: Annotated[List[DayPlan], _plan_reducer]
    final_answer: str
    
    # ============ 控制流 ============
    version: int
    errors: List[str]
    retry_count: int
    messages: Annotated[List[dict], add]
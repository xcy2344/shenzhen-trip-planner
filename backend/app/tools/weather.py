def get_shenzhen_weather(days: int = 3) -> str:
    """查询深圳未来几天的天气（模拟数据）"""
    weather_data = {
        1: "深圳明天：晴，26-32度",
        2: "深圳未来两天：多云，25-31度",
        3: "深圳未来三天：晴转多云，26-33度"
    }
    return weather_data.get(days, "深圳未来天气：晴，26-32度")
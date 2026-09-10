def recommend_shenzhen_food(keyword: str = "") -> str:
    """推荐深圳美食（模拟数据）"""
    foods = {
        "海鲜": "沙井蚝、南澳鲍鱼、海鲜大排档",
        "早茶": "肠粉、虾饺、烧卖、凤爪",
        "特色": "光明乳鸽、公明烧鹅、龙岗鸡",
        "小吃": "东门町小吃街、车公庙美食街"
    }
    
    if keyword:
        for category, items in foods.items():
            if keyword in category or keyword in items:
                return f"{category}：{items}"
        return f"未找到相关美食：{keyword}"
    
    result = "深圳美食推荐：\n"
    for category, items in foods.items():
        result += f"- {category}：{items}\n"
    return result
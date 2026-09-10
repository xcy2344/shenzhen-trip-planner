from app.tools.weather import get_shenzhen_weather
from app.tools.attractions import search_shenzhen_attractions
from app.tools.food import recommend_shenzhen_food

print("=== 天气 ===")
print(get_shenzhen_weather(3))

print("\n=== 景点 ===")
print(search_shenzhen_attractions())

print("\n=== 美食 ===")
print(recommend_shenzhen_food())
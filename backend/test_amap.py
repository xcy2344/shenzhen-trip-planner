import requests

AMAP_KEY = "ebb45d2c193bdae3f3a886909c20f196"   # 换成你实际的 Key

print("Key 长度：", len(AMAP_KEY))
print("Key 前10位：", AMAP_KEY[:10])
print("开始请求...")

try:
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": AMAP_KEY,
        "address": "深圳北站",
    }
    response = requests.get(url, params=params, timeout=10)
    print("HTTP 状态码：", response.status_code)
    print("返回内容：", response.text)
except Exception as e:
    print("出错了：", type(e).__name__, e)
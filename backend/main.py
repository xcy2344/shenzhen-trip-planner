import uvicorn
from app.api.routes import app

if __name__ == "__main__":
    print("启动深圳旅游规划服务...")
    print("接口文档：http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
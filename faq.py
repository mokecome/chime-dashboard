# -*- coding: utf-8 -*-
import os
import json
import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from typing import Dict, Any, Optional
from kufa_data import fetch_stamp_data
import math
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import litellm

load_dotenv(override=True)

litellm._turn_on_debug()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

model = LiteLlm(
    model="gpt-4o",  
    api_base=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)

# 全域變數存儲當前用戶ID
current_user_id = None

def get_user_location() -> Dict[str, str]:
    """
    獲取使用者當前經緯度
    Returns:
        {
            "latitude":  "25.0338483"
            "longitude": "121.5645283"             
        }
    """
    import requests
    try:
        # 嘗試多個 IP 定位服務，提高成功率
        services = [
            "http://ip-api.com/json/",
            "https://ipapi.co/json/",
            "https://freegeoip.app/json/"
        ]
        
        for url in services:
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                # 根據不同服務的響應格式處理
                if url.startswith("http://ip-api.com"):
                    if data.get("status") == "success":
                        return {
                            "latitude": data.get("lat"),
                            "longitude": data.get("lon"),
                            "city": data.get("city")
                        }
                elif url.startswith("https://ipapi.co"):
                    if data.get("latitude") and data.get("longitude"):
                        return {
                            "latitude": data.get("latitude"),
                            "longitude": data.get("longitude"),
                            "city": data.get("city")
                        }
                elif url.startswith("https://freegeoip.app"):
                    if data.get("latitude") and data.get("longitude"):
                        return {
                            "latitude": data.get("latitude"),
                            "longitude": data.get("longitude"),
                            "city": data.get("city")
                        }
                        
            except Exception as service_error:
                logger.warning(f"IP 定位服務 {url} 失敗: {service_error}")
                continue
        
        # 如果所有服務都失敗，返回台北作為默認位置
        logger.warning("所有 IP 定位服務都失敗，使用台北作為默認位置")
        return {
            "latitude": "25.0338",
            "longitude": "121.5645",
            "city": "Taipei"
        }
        
    except Exception as e:
        logger.error(f"IP 定位發生錯誤: {str(e)}")
        return {
            "latitude": "25.0338",
            "longitude": "121.5645",
            "city": "Taipei"
        }

def haversine(lat1, lon1, lat2, lon2):
    """
    計算兩點間的球面距離（單位：公里）
    """
    R = 6371  # 地球半徑 (公里)
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(d_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def GetUserAllStamps() -> Dict[str, Any]:
    """
    獲取用户所有尚未獲得的集章名(stamp_name) 活動名(activity_name)  集章地址(address)
    
    輸出:
         [
          {'stamp_name': '智慧景區', 'activity_name': '數位觀光體驗集點''address': '804 高雄市鼓山區蓬萊路 99 號'}, 
          {'stamp_name': '旅宿體驗站', 'activity_name': '數位觀光體驗集點', 'address': '804 高雄市鼓山區蓬萊路 99 號'},
                ...
         ]
    """
    global current_user_id
    if not current_user_id:
        return []
        
    stamp_data = fetch_stamp_data(current_user_id)
    locations = []
    for item in stamp_data:
        s_time = item["s_time"]
        e_time = item["e_time"]
        address = item.get("stamp_address") or ""
        locations.append({
                "stamp_name": item["stamp_name"],
                "activity_name": item["activity_name"],
                "activity_time": s_time + '~' + e_time,
                "address": address,
                "store_name": item["store_name"]})

    return locations

def GetUserNearStamps() -> Dict[str, Any]:
    """
    獲取使用者 「附近 / 周邊 / 周遭」 尚未獲得的集章名(stamp_name) 活動名(activity_name)  集章地址(address) ,距離由近到遠排序
    
    輸出:
         [
          {'stamp_name': '智慧景區', 'activity_name': '數位觀光體驗集點''address': '804 高雄市鼓山區蓬萊路 99 號'..}, 
          {'stamp_name': '旅宿體驗站', 'activity_name': '數位觀光體驗集點', 'address': '804 高雄市鼓山區蓬萊路 99 號'..},
                ...
         ]
    """
    global current_user_id
    if not current_user_id:
        return []
        
    CITY_MAP = {
        "Taipei": "台北",
        "New Taipei City": "新北",
        "Taichung": "台中",
        "Tainan": "台南",
        "Kaohsiung": "高雄",
        "Keelung": "基隆",
        "Hsinchu": "新竹",
        "Chiayi": "嘉義",
        "Taoyuan": "桃園",
        "Miaoli": "苗栗",
        "Changhua": "彰化",
        "Nantou": "南投",
        "Yunlin": "雲林",
        "Pingtung": "屏東",
        "Yilan": "宜蘭",
        "Hualien": "花蓮",
        "Taitung": "台東",
        "Penghu": "澎湖",
        "Kinmen": "金門",
        "Lienchiang": "連江",
    }

    location = get_user_location()
    if not location["latitude"] or not location["longitude"]:
        return []
        
    user_lat = float(location["latitude"])
    user_lon = float(location["longitude"])
    user_city_zh = CITY_MAP.get(location["city"], "")
    
    stamp_data = fetch_stamp_data(current_user_id)
    near_locations = []
    
    for item in stamp_data:
        s_time = item["s_time"]
        e_time = item["e_time"]
        lat = item["latitude"]
        lon = item["longitude"]
        address = item.get("stamp_address") or ""
        
        if user_city_zh and user_city_zh in address:
            if lat and lon:
                distance = haversine(user_lat, user_lon, float(lat), float(lon))
                near_locations.append({
                    "stamp_name": item["stamp_name"],
                    "activity_name": item["activity_name"],
                    "activity_time": s_time + '~' + e_time,
                    "address": address,
                    "store_name": item["store_name"],
                    "distance": round(distance, 2)
                })
    
    top3 = sorted(near_locations, key=lambda x: x["distance"])[:3]
    return top3

agent = Agent(
    name="chatbot",
    model=model,
    instruction='''
    你是一個智能助手。請按照以下流程工作：

    1. 對於一般問候（如"你好"、"嗨"等），友善回應
    2. 如果詢問集章相關問題
       -集章地點相關問題，調用 GetUserUnobtainedStamps 查看用户還未獲得的集章,提供最佳路徑(最近距離)
        活動相關：
        (1). 顯示活動名稱
        (2). 顯示活動時間～結束時間
        (3). 顯示活動地址（若無地址則隱藏）

        集章相關：
        (1). 提供還沒集到的集章
        (2). 顯示集章名稱
        (3). 顯示集章地點
        (4). 顯示距離＿km
       
       -會給予建議路線 和 到達時間 


       q1:我已經到現場了，但系統顯示我不在集章範圍內，怎麼辦？
       a1:若您確實已抵達指定集章地點，卻因 GPS 訊號不穩或其他因素無法成功集章。
          -方法一：
            (1)私訊臉書粉絲專頁
            (2)工作人員將在收到訊息後進行審核，確認無誤後會協助您補登集章
            (3)申請時建議附上現場照片加速審核流程

          -方法二：
            (1)於活動現場找到 QR Code 資訊編碼
            (2)於活動頁點擊「開啟相機」
            (3)選擇「手動輸入 QR Code 資訊」來獲得集章 
       q2:如何集章？

       q3:如何領取獎品？

       q4:如何查詢我的集章進度？


    3. 對於與q1-q7相似的問題，以a1-a7參考直接回答
       q1:如何註冊新帳號並登入？
       a1:(1)信箱註冊登入：
            -輸入欲註冊的 Email，並完成信箱驗證。
            -請至信箱收取驗證碼，若沒看到信件，可以至垃圾信件匣確認。
            -經驗證後，設置帳户密碼、姓名，並確保資訊無誤，點擊「同意並註冊」，即可使用信箱和密碼登入漫遊寶島。
          (2)第三方帳號登入：
            -你可使用 Google、LINE、Facebook 帳號等方式快速登入。

       q2:可以同時綁定多個第三方帳號進行登入嗎？
       a2:一組 Email 視為一個會員信箱帳號，而一組信箱可以同時連結多種快速登入的方式。
          當系統顯示「是否綁定此 Email 帳號？」，代表先前已使用該信箱進行註冊，請接續設定漫遊寶島平台密碼，未來將可以使用第三方帳號進行快速登入或是一般登入等多種方式。    

       q3:忘記密碼怎麼辦？如何變更密碼?
       a3:忘記密碼：
            1. 你可使用 Google、LINE、Facebook 帳號等方式，當系統判定為相同的 Email 帳號，則可進行快速登入。
            2. 輸入你想找回的會員信箱帳號，確認 Email 無誤後，點選「忘記密碼」，至信箱收取 4 位數驗證碼，經驗證後即可重設漫遊寶島的密碼。

            變更密碼
            -登入會員信箱帳號後，點選「會員中心」並進入「帳號設定」頁面，即可修改你的密碼。

       q4:登入時 Google 禁止存取該怎麼做？
       a4:如果你使用的是「私密瀏覽模式」，通常就會出現此情況。建議你可以切換成「一般瀏覽視窗」或是可以嘗試使用其他瀏覽器來開啟註冊或登入頁面。

       q5:登入時顯示此帳號已被綁定？
       a5:系統顯示「是否綁定此 Email 帳號？」，代表先前已使用該信箱進行註冊，請接續設定漫遊寶島平台密碼，未來將可以使用第三方帳號進行快速登入或是一般登入等多種方式。

       q6:一個活動只能集章一次嗎？
       a6:一組 Email 視為一個會員信箱帳號，每個信箱在同一檔活動中，僅能完成一次集章任務；若使用不同的信箱登入或註冊，即可重新參與集章活動並獲得獎勵。

       q7:當相機無法掃描 QR Code 可以怎麼辦？
       a7:當一般相機無法掃描 QR Code 時，建議可以參考以下的解決方式：
          -iPhone／IOS版
           請前往 iPhone 內建的「設定」，下滑找到「相機」功能，並檢查是否有開啟「掃描行動條碼」的功能，沒有的話記得將它啟用喔！
          -Android 系統
           當一般相機無法使用時，建議使用 Google 瀏覽器的內建掃描功能，或是搜尋「漫遊寶島」官方網站，進行快速登入或註冊，亦可透過活動內建相機掃描 QR Code集章，操作更順暢！
    
    # 其他注意事項
    請用繁體中文與用户交流。
    若這個問題不知道就回答不知道。
    ''',
    description="回答用户的問題。",
    tools=[GetUserNearStamps, GetUserAllStamps]
)

# WebSocket 和 FastAPI 部分保持不變，但修正消息處理
async def create_or_get_session(runner, user_id, session_id=None):
    """創建新會話或獲取已有會話，返回實際的 session_id"""
    if session_id:
        session = await runner.session_service.get_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        if session:
            print(f"📋 使用已存在的 Session: {session_id}")
            return session_id
        else:
            print(f"🔧 Session {session_id} 不存在，創建新會話...")
    else:
        print(f"🔧 自動創建新會話...")
    
    new_session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id
    )
    
    print(f"✅ 會話創建成功，Session ID: {new_session.id}")
    return new_session.id

async def call_agent_async_ws(query: str, runner, user_id: str, session_id: str, websocket: WebSocket):
    """通過 WebSocket 發送用戶的問題給 Agent 並實時返回響應"""
    
    # 設置全域 USER_ID，讓工具函數可以使用
    global current_user_id
    current_user_id = user_id
    
    logger.info(f"用戶 {user_id} 發送問題: {query}")
    
    # 直接使用用戶的問題，不需要附加 USER_ID
    content = types.Content(role='user', parts=[types.Part(text=query)])
    
    run_config = RunConfig(streaming_mode=StreamingMode.SSE)
    
    accumulated_text = ""
    
    try:
        await websocket.send_json({
            "type": "start",
            "message": "開始處理您的問題..."
        })
        
        async for event in runner.run_async(
            user_id=user_id, 
            session_id=session_id, 
            new_message=content, 
            run_config=run_config
        ):
            if event.content and event.content.parts and event.content.parts[0].text:
                current_text = event.content.parts[0].text
                
                if event.partial:
                    if current_text.startswith(accumulated_text):
                        delta_text = current_text[len(accumulated_text):]
                        if delta_text:
                            await websocket.send_json({
                                "type": "partial",
                                "content": delta_text
                            })
                            accumulated_text = current_text
                    else:
                        await websocket.send_json({
                            "type": "partial",
                            "content": current_text
                        })
                        accumulated_text += current_text
                else:
                    if current_text.startswith(accumulated_text):
                        remaining_text = current_text[len(accumulated_text):]
                        if remaining_text:
                            await websocket.send_json({
                                "type": "partial",
                                "content": remaining_text
                            })
                    elif not accumulated_text:
                        await websocket.send_json({
                            "type": "complete",
                            "content": current_text
                        })
                    
                    if hasattr(event, 'turn_complete') and event.turn_complete:
                        break
                    elif not event.partial and (not hasattr(event, 'turn_complete') or event.turn_complete is None):
                        break
        
        await websocket.send_json({
            "type": "end",
            "message": "響應完成"
        })
        
    except Exception as e:
        logger.error(f"處理消息時發生錯誤: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"處理時發生錯誤: {str(e)}"
        })

app = FastAPI(
    title="FAQ ChatBot WebSocket API",
    description="基於 Google ADK 的聊天客服系統",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"用戶 {user_id} 已連接")
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"用戶 {user_id} 已斷開連接")
    
    async def send_message(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)

manager = ConnectionManager()

@app.get("/")
async def root():
    return {
        "message": "FAQ ChatBot WebSocket API",
        "endpoints": {
            "websocket": "/ws/chat?user_id={user_id}",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "active_connections": len(manager.active_connections)}

@app.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket, 
    user_id: str = Query(..., description="用戶ID")
):
    """WebSocket 聊天端點"""
    
    await manager.connect(websocket, user_id)
    session_service = InMemorySessionService()

    runner = Runner(
        agent=agent,
        app_name='test_app',
        session_service=session_service,
    )
    
    session_id = None
    conversation_count = 0
    
    try:
        await websocket.send_json({
            "type": "welcome",
            "message": "歡迎使用 FAQ 智能助手！",
            "user_id": user_id
        })
        
        session_id = await create_or_get_session(runner, user_id)
        await websocket.send_json({
            "type": "session_created",
            "session_id": session_id
        })
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                # 修正：直接使用用戶的問題，不附加 USER_ID
                query = message.get("query", "").strip()
                
                if not query:
                    await websocket.send_json({
                        "type": "error",
                        "message": "請提供有效的問題"
                    })
                    continue
                
                conversation_count += 1
                
                await websocket.send_json({
                    "type": "info",
                    "conversation_count": conversation_count,
                    "session_id": session_id
                })
                
                await call_agent_async_ws(query, runner, user_id, session_id, websocket)
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "無效的 JSON 格式"
                })
            except Exception as e:
                logger.error(f"處理消息時發生錯誤: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"處理錯誤: {str(e)}"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        logger.info(f"用戶 {user_id} 斷開連接 (會話: {session_id})")
    except Exception as e:
        logger.error(f"WebSocket 錯誤: {str(e)}")
        manager.disconnect(user_id)

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "faq:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )

    

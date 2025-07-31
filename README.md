# 集章活動智能助手專案說明

## 專案簡介

本專案是一個結合 FastAPI、Google ADK 及 OpenAI GPT-4o 的智能聊天助手，主要功能為：
- 根據使用者 IP 位置，查詢尚未獲得的集章地點與活動資訊
- 計算使用者與各集章地點的距離，推薦最近的集章點
- 支援多輪對話、活動查詢、集章進度查詢等

---

## 目錄結構

- `faq.py`：主程式，包含智能助手邏輯、距離計算、API 入口
- `kufa_data.py`：資料庫查詢模組，負責從 MySQL 取得集章活動資料

---

## 主要功能說明

### 1. 集章資料查詢（kufa_data.py）

- 使用 `fetch_stamp_data(USER_ID)` 連接 MySQL，查詢使用者尚未獲得的集章活動資料。
- 回傳內容包含：集章名稱、活動名稱、地址、經緯度、活動時間等。

### 2. 使用者定位與距離計算（faq.py）

- `get_user_location()`：根據使用者 IP 取得目前城市與經緯度。
- `haversine(lat1, lon1, lat2, lon2)`：計算兩點間球面距離（公里）。
- `GetUserUnobtainedStamps(USER_ID, NEAR)`：根據使用者位置，查詢尚未獲得的集章，並依距離排序，支援「周邊」查詢（NEAR=True 時只回傳最近三個）。

### 3. 智能對話（faq.py）

- 整合 Google ADK Agent，支援多輪對話、活動查詢、集章進度查詢等。
- 可用命令列或 WebSocket 進行互動。

---

## 環境需求

- Python 3.12+
- MySQL 資料庫（需設定連線資訊）
- 依賴套件：`pymysql`, `requests`, `google-adk`, `openai`, `fastapi`, `uvicorn`, `python-dotenv`

安裝依賴：
```bash
pip install pymysql requests fastapi uvicorn python-dotenv
```

---

## 使用方式

### 1. 啟動命令列互動

```bash
python faq.py
```


from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from tinydb import TinyDB, Query
import requests
import datetime
import os

# Cố định thư mục gốc theo vị trí file app.py này
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()
db = TinyDB(os.path.join(BASE_DIR, 'history_db.json'))
History = Query()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class TranslateRequest(BaseModel):
    text: str

@app.post("/translate")
def translate_logic(request: TranslateRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui lòng nhập Key")

    # Cấu hình Antigravity của bạn (Support biến môi trường khi deploy)
    ANTIGRAVITY_URL = os.getenv("ANTIGRAVITY_URL", "http://127.0.0.1:8045/v1/chat/completions") 

    
    payload = {
        "model": "gemini-3-flash-agent",
        "messages": [
            {
                "role": "system", 
                "content": "You are a specialized Vietnamese-Chinese translator. If input is Vietnamese, translate to Chinese (Mandarin). If input is Chinese, translate to Vietnamese. Return ONLY the translation."
            },
            {"role": "user", "content": request.text}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(
            ANTIGRAVITY_URL, 
            json=payload, 
            headers={"Authorization": f"Bearer {x_api_key}"},
            timeout=90 # Đảm bảo chết trước 100s của Cloudflare để báo lỗi rõ ràng
        )
        result = response.json()['choices'][0]['message']['content'].strip()

        # Lưu lịch sử và cập nhật xếp hạng (count)
        existing = db.get(History.original == request.text)
        if existing:
            db.update({'count': existing['count'] + 1, 'time': str(datetime.datetime.now())}, History.original == request.text)
        else:
            db.insert({
                'original': request.text, 
                'translated': result, 
                'count': 1, 
                'time': str(datetime.datetime.now())
            })

        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def get_history():
    # Trả về 10 câu được dùng nhiều nhất
    all_data = db.all()
    sorted_data = sorted(all_data, key=lambda x: x['count'], reverse=True)
    return sorted_data[:10]

if __name__ == "__main__":
    import uvicorn
    # Sử dụng 0.0.0.0 để cho phép truy cập từ các thiết bị khác (Remote, Lan, v.v...)
    uvicorn.run(app, host="0.0.0.0", port=8000)
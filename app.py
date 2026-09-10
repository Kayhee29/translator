from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from tinydb import TinyDB, Query
import requests
import datetime
import os
import json
import re

# Cố định thư mục gốc theo vị trí file app.py này
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_ANTIGRAVITY_URL = "http://192.168.1.179:8045/v1/chat/completions"

app = FastAPI()
db = TinyDB(os.path.join(BASE_DIR, 'history_db.json'))
xianyu_db = TinyDB(os.path.join(BASE_DIR, 'xianyu_history_db.json'))
quickchat_db = TinyDB(os.path.join(BASE_DIR, 'quickchat_db.json'))
History = Query()

# --- 1. Thêm Database mới (Chèn vào đoạn khai báo DB phía trên) ---
goofish_db = os.path.join(BASE_DIR, 'goofish_db.json')
g_db = TinyDB(goofish_db)
Product = Query()

# --- 1. Cấu hình Database cho Product (Đặt gần đoạn TinyDB hiện tại) ---
product_db = TinyDB(os.path.join(BASE_DIR, 'goofish_data.json'))
ProductTable = product_db.table('product_product')
ImageTable = product_db.table('product_img')
TagTable = product_db.table('tags')
ProdQuery = Query()
TagQuery = Query()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def read_index():
    return FileResponse(os.path.join(BASE_DIR, 'index.html'))


class TranslateRequest(BaseModel):
    text: str
    target_language: str | None = None
    model: str | None = None
    verify_back_translation: bool = False

class XianyuTranslateRequest(BaseModel):
    text: str
    session_id: str | None = None

class XianyuBatchTranslateRequest(BaseModel):
    texts: list[str]
    session_id: str | None = None

class QuickChatRequest(BaseModel):
    chinese: str
    vietnamese: str

# --- 2. Thêm Model (Chèn vào đoạn khai báo class BaseModel) ---
class GoofishCaptureRequest(BaseModel):
    payload: dict

# Cập nhật Model để hỗ trợ cập nhật tag thủ công
class TagUpdateRequest(BaseModel):
    product_id: str
    tags: list[str]

# Model cho cấu hình Tag
class TagConfig(BaseModel):
    name: str
    color: str

# --- 2. Schema cho Request từ Extension ---
class GoofishDetailPayload(BaseModel):
    data: dict

class ChatProductPayload(BaseModel):
    data: dict

class DomProductPayload(BaseModel):
    product_id: str
    title: str
    price: str
    city: str
    description: str | None = ""
    images: list[str]


class ChatTranslateMessage(BaseModel):
    id: str
    role: str
    content: str


class ChatTranslateRequest(BaseModel):
    target_language: str
    messages: list[ChatTranslateMessage]
    message_ids_to_translate: list[str]
    model: str | None = None
    verify_back_translation: bool = False


def split_bulk_paste_into_messages(text, role, id_prefix="bulk"):
    chunks = [chunk.strip() for chunk in re.split(r"\r?\n\s*\r?\n+", text) if chunk.strip()]
    return [
        {"id": f"{id_prefix}-{index}", "role": role, "content": chunk}
        for index, chunk in enumerate(chunks, start=1)
    ]


def build_reduced_context_window(messages, message_ids_to_translate, prior_limit=5):
    id_to_index = {message["id"]: index for index, message in enumerate(messages)}
    missing_ids = [message_id for message_id in message_ids_to_translate if message_id not in id_to_index]
    if missing_ids:
        raise ValueError(f"Unknown message ids: {missing_ids}")

    target_indexes = sorted(id_to_index[message_id] for message_id in message_ids_to_translate)
    if target_indexes[-1] - target_indexes[0] + 1 > len(target_indexes):
        raise ValueError("message_ids_to_translate must form a contiguous block")
    start_index = max(0, target_indexes[0] - prior_limit)
    end_index = target_indexes[-1] + 1
    return messages[start_index:end_index]


def build_chat_translate_prompt(target_language, context_messages, message_ids_to_translate, verify_back_translation: bool = False):
    conversation_lines = []
    for message in context_messages:
        conversation_lines.append(
            f"[{message['id']}] role={message['role']}\n{message['content']}"
        )

    conversation_block = "\n\n".join(conversation_lines)
    ids_block = ", ".join(message_ids_to_translate)

    if verify_back_translation:
        verify_instruction = (
            "If the target language is NOT Vietnamese, and the detected source language of the message IS Vietnamese, "
            "translate your primary translation back to Vietnamese and provide it in 'back_translated_text'. "
            "Otherwise, 'back_translated_text' must be empty string \"\".\n"
        )
        json_example = '{"results":[{"id":"message-id","translated_text":"...","source_language":"...","back_translated_text":"..."}]}'
    else:
        verify_instruction = "The field 'back_translated_text' must be empty string \"\".\n"
        json_example = '{"results":[{"id":"message-id","translated_text":"...","source_language":"...","back_translated_text":""}]}'

    return (
        "You are a context-aware translator.\n"
        f"Translate only these message ids: {ids_block}\n"
        f"Target language: {target_language}\n"
        "Detect the source language for each translated message.\n"
        "Use the nearby conversation context to preserve meaning, tone, and references.\n"
        f"{verify_instruction}"
        f"Return ONLY valid JSON in the form {json_example}\n\n"
        f"Conversation:\n{conversation_block}"
    )


def build_models_url(url: str) -> str:
    stripped_url = url.rstrip("/")
    if stripped_url.endswith("/chat/completions"):
        return stripped_url[:-len("/chat/completions")] + "/models"
    elif stripped_url.endswith("/v1"):
        return stripped_url + "/models"
    else:
        raise ValueError(f"Unsupported models URL base: {url}")


def normalize_models_response(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError("Payload 'data' must be a non-empty list")

    normalized = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Model item must be a dictionary")
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("Model item must have a non-empty string 'id'")
        model_name = item.get("name")
        if not isinstance(model_name, str) or not model_name.strip():
            model_name = model_id
        normalized.append({"id": model_id, "name": model_name})
    return normalized


def strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def parse_sse_chat_completion(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError("Upstream SSE response must be text")

    content_parts = []
    saw_sse_event = False

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue

        data = line[5:].strip()
        saw_sse_event = True
        if data == "[DONE]":
            continue

        event = json.loads(data)
        choices = event.get("choices") if isinstance(event, dict) else None
        if not isinstance(choices, list) or not choices:
            continue

        choice = choices[0]
        delta = choice.get("delta") if isinstance(choice, dict) else None
        if not isinstance(delta, dict):
            continue

        content = delta.get("content")
        if content is None:
            continue
        if not isinstance(content, str):
            raise ValueError("SSE content must be a string")
        content_parts.append(content)

    if not saw_sse_event:
        raise ValueError("Upstream response is neither JSON nor SSE")
    if not content_parts:
        raise HTTPException(status_code=502, detail="Upstream returned an empty SSE response")

    return {"choices": [{"message": {"content": "".join(content_parts)}}]}


def parse_chat_completion_response(response) -> dict:
    try:
        return response.json()
    except ValueError:
        return parse_sse_chat_completion(response.text)


def parse_translation_payload(content: str) -> tuple[dict | None, str]:
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=500, detail="AI did not return valid JSON")

    cleaned = strip_markdown_fence(content).strip()
    if not cleaned:
        raise HTTPException(status_code=500, detail="AI did not return valid JSON")

    looks_like_object = cleaned.startswith("{")

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        if looks_like_object:
            raise HTTPException(status_code=500, detail="AI did not return valid JSON")
        return None, cleaned

    if isinstance(parsed, dict):
        return parsed, ""

    if looks_like_object:
        raise HTTPException(status_code=500, detail="Invalid translation response format")

    return None, cleaned



@app.get("/models")
def list_models(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui long nhap Key")
    try:
        models_url = build_models_url(os.getenv("ANTIGRAVITY_URL", DEFAULT_ANTIGRAVITY_URL))
        response = requests.get(
            models_url,
            headers={"Authorization": f"Bearer {x_api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        return {"models": normalize_models_response(response.json())}
    except (ValueError, requests.RequestException, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Không thể lấy danh sách model: {exc}")


@app.post("/capture_dom_product")
def capture_dom_product(payload: DomProductPayload, x_api_key: str = Header(None)):
    product_id = payload.product_id
    
    # Hàm dịch dùng chung
    def translate_internal(text):
        if not text or not x_api_key: return text
        existing = xianyu_db.get(History.original == text)
        if existing: return existing['translated']
        try:
            payload_ai = {
                "model": "gemini-3-flash",
                "messages": [
                    {"role": "system", "content": "You are a specialized Vietnamese-Chinese translator. If input is Chinese, translate to Vietnamese. Return ONLY the translation."},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.2
            }
            response = requests.post(os.getenv("ANTIGRAVITY_URL", DEFAULT_ANTIGRAVITY_URL), json=payload_ai, headers={"Authorization": f"Bearer {x_api_key}"}, timeout=10)
            result = response.json()['choices'][0]['message']['content'].strip()
            xianyu_db.insert({'original': text, 'translated': result, 'count': 1, 'time': str(datetime.datetime.now())})
            return result
        except Exception as e:
            print(f"AI Translation Error (DOM): {e}")
            return text

    translated_title = translate_internal(payload.title)
    # Ở DOM fallback, payload.description có thể rỗng, nhưng cứ dịch
    description = payload.description or ""
    translated_desc = translate_internal(description)

    final_title = f"{translated_title}\n\n[Trung]: {payload.title}" if payload.title and translated_title and translated_title != payload.title else payload.title
    final_desc = f"{translated_desc}\n\n[Trung]: {description}" if description and translated_desc and translated_desc != description else description

    product_info = {
        "product_id": product_id,
        "title": final_title,
        "price": payload.price,
        "status": "Available",
        "city": payload.city,
        "description": final_desc,
        "updated_at": str(datetime.datetime.now())
    }

    existing_prod = ProductTable.get(ProdQuery.product_id == product_id)
    if existing_prod:
        # CHỈ cập nhật nếu dữ liệu cũ đang trống để tránh ghi đè dữ liệu tốt từ API
        update_data = {}
        if not existing_prod.get("title") or "为你推荐" in existing_prod.get("title", "") or existing_prod.get("title") == "Unknown Title":
            update_data["title"] = product_info["title"]
        if not existing_prod.get("price") or existing_prod.get("price") == "0":
            update_data["price"] = product_info["price"]
        if not existing_prod.get("city"):
            update_data["city"] = product_info["city"]
        if not existing_prod.get("description"):
            update_data["description"] = product_info["description"]
        
        if update_data:
            update_data["updated_at"] = str(datetime.datetime.now())
            ProductTable.update(update_data, ProdQuery.product_id == product_id)
    else:
        product_info["custom_tags"] = []
        ProductTable.insert(product_info)

    new_img_count = 0
    for img_url in payload.images:
        is_img_exist = ImageTable.get((ProdQuery.product_id == product_id) & (ProdQuery.url == img_url))
        if not is_img_exist:
            ImageTable.insert({
                "product_id": product_id,
                "url": img_url,
                "width": 0,
                "height": 0,
                "captured_at": str(datetime.datetime.now())
            })
            new_img_count += 1

    return {"status": "success", "new_images": new_img_count}

@app.post("/capture_chat_product")
def capture_chat_product(payload: ChatProductPayload, x_api_key: str = Header(None)):
    try:
        data_root = payload.data.get("data", {})
        common_data = data_root.get("commonData", {})
        middle_data = data_root.get("middle", {}).get("data", {})
        
        product_id = common_data.get("itemId")
        if not product_id:
            raise HTTPException(status_code=400, detail="Không tìm thấy ID sản phẩm")
            
        product_id = str(product_id)
        item_pre_info_str = common_data.get("itemPreInfo")
        if not item_pre_info_str:
            item_pre_info_str = "{}"
        
        try:
            item_pre_info = json.loads(item_pre_info_str)
        except:
            item_pre_info = {}
            
        title = item_pre_info.get("title")
        description = item_pre_info.get("postInfo")
        
        # Translate title and description internally if API key is provided
        def translate_internal(text):
            if not text or not x_api_key: return text
            existing = xianyu_db.get(History.original == text)
            if existing: return existing['translated']
            try:
                payload = {
                    "model": "gemini-3.1-flash-lite-preview",
                    "messages": [
                        {"role": "system", "content": "You are a specialized Vietnamese-Chinese translator. If input is Chinese, translate to Vietnamese. Return ONLY the translation."},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.2
                }
                response = requests.post(DEFAULT_ANTIGRAVITY_URL, json=payload, headers={"Authorization": f"Bearer {x_api_key}"}, timeout=10)
                result = response.json()['choices'][0]['message']['content'].strip()
                xianyu_db.insert({'original': text, 'translated': result, 'count': 1, 'time': str(datetime.datetime.now())})
                return result
            except:
                return text

        translated_title = translate_internal(title)
        translated_desc = translate_internal(description)
        
        # Lưu cả tiếng Việt và tiếng Trung (nếu dịch thành công và khác bản gốc)
        final_title = f"{translated_title}\n\n[Trung]: {title}" if title and translated_title and translated_title != title else title
        final_desc = f"{translated_desc}\n\n[Trung]: {description}" if description and translated_desc and translated_desc != description else description
            
        # 1. Xử lý bảng product_product
        product_info = {
            "product_id": product_id,
            "title": final_title,
            "price": item_pre_info.get("soldPrice") or middle_data.get("price"),
            "status": "Available", # Default
            "city": middle_data.get("tips"),
            "description": final_desc,
            "updated_at": str(datetime.datetime.now())
        }

        existing_prod = ProductTable.get(ProdQuery.product_id == product_id)
        if existing_prod:
            ProductTable.update(product_info, ProdQuery.product_id == product_id)
        else:
            product_info["custom_tags"] = []
            ProductTable.insert(product_info)

        # 2. Xử lý bảng product_img
        image_infos_str = item_pre_info.get("imageInfos")
        if not image_infos_str:
            image_infos_str = "[]"
            
        try:
            image_list = json.loads(image_infos_str)
        except:
            image_list = []
            
        new_img_count = 0
        for img in image_list:
            img_url = img.get("url")
            if img_url:
                is_img_exist = ImageTable.get((ProdQuery.product_id == product_id) & (ProdQuery.url == img_url))
                if not is_img_exist:
                    ImageTable.insert({
                        "product_id": product_id,
                        "url": img_url,
                        "width": img.get("widthSize"),
                        "height": img.get("heightSize"),
                        "captured_at": str(datetime.datetime.now())
                    })
                    new_img_count += 1

        return {
            "status": "success",
            "product_id": product_id,
            "new_images": new_img_count
        }

    except Exception as e:
        print(f"Error parsing chat product: {e}")
        raise HTTPException(status_code=500, detail="Lỗi xử lý dữ liệu chat")

@app.post("/translate")
def translate_logic(request: TranslateRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui lòng nhập Key")

    if request.target_language is not None and not request.target_language.strip():
        raise HTTPException(status_code=400, detail="target_language must not be empty")

    if request.model is not None and not request.model.strip():
        raise HTTPException(status_code=400, detail="model must not be empty")

    selected_model = (request.model.strip() if request.model else None) or "gemini-3-flash-agent"

    if request.target_language is None:
        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a specialized Vietnamese-Chinese translator. If input is Vietnamese, translate to Chinese (Mandarin). If input is Chinese, translate to Vietnamese. Return ONLY the translation."
                },
                {"role": "user", "content": request.text}
            ],
            "temperature": 0.2
        }
    else:
        target_lang = request.target_language.strip()
        system_content = (
            "You are a professional translator.\n"
            f"Target language: {target_lang}\n"
            "Detect the source language of the input text.\n"
            f"Translate the input text into {target_lang}.\n"
        )
        if request.verify_back_translation:
            system_content += (
                "If the target language is NOT Vietnamese, and the detected source language IS Vietnamese, "
                "translate your primary translation back to Vietnamese and provide it in 'back_translated_text'. "
                "Otherwise, 'back_translated_text' must be empty string \"\".\n"
            )
        else:
            system_content += "'back_translated_text' must be empty string \"\".\n"

        system_content += (
            "Return ONLY valid JSON in the format:\n"
            '{"result": "...", "source_language": "...", "back_translated_text": "..."}'
        )

        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": request.text}
            ],
            "temperature": 0.2
        }

    antigravity_url = os.getenv("ANTIGRAVITY_URL", DEFAULT_ANTIGRAVITY_URL)

    try:
        response = requests.post(
            antigravity_url,
            json=payload,
            headers={"Authorization": f"Bearer {x_api_key}"},
            timeout=90
        )
        api_response = parse_chat_completion_response(response)
        if 'choices' not in api_response:
            raise HTTPException(status_code=500, detail=f"Antigravity API Error: {api_response}")

        raw_content = api_response['choices'][0]['message'].get('content', '')

        if request.target_language is None:
            result = raw_content.strip()
            source_language = ""
            back_translated_text = ""
        else:
            parsed, fallback_text = parse_translation_payload(raw_content)

            if parsed is not None:
                if not isinstance(parsed, dict) or "result" not in parsed:
                    raise HTTPException(status_code=500, detail="Invalid translation response format")

                result = parsed.get("result")
                if not isinstance(result, str):
                    raise HTTPException(status_code=500, detail="Result must be a string")

                source_language = parsed.get("source_language")
                if source_language is None:
                    source_language = ""
                elif not isinstance(source_language, str):
                    source_language = str(source_language)

                back_translated_text = parsed.get("back_translated_text")
                if back_translated_text is None:
                    back_translated_text = ""
                elif not isinstance(back_translated_text, str):
                    raise HTTPException(status_code=500, detail="Invalid back_translated_text format")
            else:
                result = fallback_text
                source_language = ""
                back_translated_text = ""

        # Lưu lịch sử và cập nhật xếp hạng (count)
        existing = db.get(History.original == request.text)
        if existing:
            db.update({
                'count': existing['count'] + 1,
                'time': str(datetime.datetime.now())
            }, History.original == request.text)
        else:
            db.insert({
                'original': request.text,
                'translated': result,
                'count': 1,
                'time': str(datetime.datetime.now())
            })

        if request.target_language is None:
            return {"result": result}

        return {
            "result": result,
            "source_language": source_language,
            "back_translated_text": back_translated_text,
        }
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI did not return valid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate_xianyu")
def translate_xianyu_logic(request: XianyuTranslateRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui lòng nhập Key")

    # Kiểm tra cache trước (Tránh gọi AI tốn kém)
    existing = xianyu_db.get(History.original == request.text)
    if existing:
        xianyu_db.update({
            'count': existing.get('count', 0) + 1, 
            'time': str(datetime.datetime.now()),
            'session_id': request.session_id or existing.get('session_id')
        }, History.original == request.text)
        print(f"CACHE HIT (Single): {request.text}")
        return {"result": existing['translated']}

    # Cấu hình Antigravity của bạn (Support biến môi trường khi deploy)
    ANTIGRAVITY_URL = os.getenv("ANTIGRAVITY_URL", DEFAULT_ANTIGRAVITY_URL) 

    
    payload = {
        "model": "gemini-3-flash",
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
        try:
            api_response = response.json()
        except ValueError:
            raise Exception(f"Failed to parse Antigravity Response. HTTP {response.status_code}. Body: {response.text}")
        if 'choices' not in api_response:
            # Throw explicitly formatted error if structural properties are missing
            raise Exception(f"Antigravity API Error: {api_response}")
        
        result = api_response['choices'][0]['message']['content'].strip()

        # Lưu lịch sử lần đầu
        xianyu_db.insert({
            'original': request.text, 
            'translated': result, 
            'count': 1, 
            'time': str(datetime.datetime.now()),
            'session_id': request.session_id
        })

        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate_xianyu_batch")
def translate_xianyu_batch_logic(request: XianyuBatchTranslateRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui lòng nhập Key")

    ANTIGRAVITY_URL = os.getenv("ANTIGRAVITY_URL", DEFAULT_ANTIGRAVITY_URL) 

    if not request.texts:
        return {"results": []}

    results = [None] * len(request.texts)
    missing_dict = {}

    for i, original_text in enumerate(request.texts):
        existing = xianyu_db.get(History.original == original_text)
        if existing:
            results[i] = existing['translated']
            xianyu_db.update({
                'count': existing.get('count', 0) + 1, 
                'time': str(datetime.datetime.now()),
                'session_id': request.session_id or existing.get('session_id')
            }, History.original == original_text)
        else:
            missing_dict[str(i)] = original_text

    if not missing_dict:
        print("CACHE HIT (Batch ALL)")
        return {"results": results}

    prompt = f"You are a specialized Vietnamese-Chinese translator. Translate the values of this JSON object to Chinese (Mandarin) if Vietnamese, or to Vietnamese if Chinese. Keep the JSON structure and keys absolutely identical. VERY IMPORTANT: Return ONLY valid parseable JSON, no markdown formatting or backticks around it:\n\n{json.dumps(missing_dict, ensure_ascii=False)}"

    payload = {
        "model": "gemini-3-flash",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(
            ANTIGRAVITY_URL, 
            json=payload, 
            headers={"Authorization": f"Bearer {x_api_key}"},
            timeout=120
        )
        api_response = response.json()
        if 'choices' not in api_response:
            raise Exception(f"Antigravity API Error: {api_response}")
        
        result_text = strip_markdown_fence(api_response['choices'][0]['message']['content'])
        
        try:
            translated_dict = json.loads(result_text)
        except json.JSONDecodeError:
            print("Failed to decode JSON from AI:", result_text)
            raise Exception("AI did not return valid JSON.")

        for i_str, original_text in missing_dict.items():
            i = int(i_str)
            translated = translated_dict.get(i_str, "Lỗi dịch")
            results[i] = translated
            
            xianyu_db.insert({
                'original': original_text, 
                'translated': translated, 
                'count': 1, 
                'time': str(datetime.datetime.now()),
                'session_id': request.session_id
            })

        for j in range(len(results)):
            if results[j] is None:
                results[j] = "Lỗi dịch (Trống)"

        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def get_history():
    # Trả về 10 câu được dùng nhiều nhất (Bản gốc)
    all_data = db.all()
    sorted_data = sorted(all_data, key=lambda x: x.get('count', 0), reverse=True)
    return sorted_data[:10]

@app.get("/history_xianyu")
def get_history_xianyu(session_id: str | None = None):
    # Trả về lịch sử chat của Xianyu
    all_data = xianyu_db.all()
    
    # Lọc theo sessionId nếu Client có gửi lên
    if session_id:
        all_data = [item for item in all_data if item.get('session_id') == session_id]
        
    # Sắp xếp theo phiên bản mới nhất thay vì count, vì Xianyu ưu tiên dòng timeline
    sorted_data = sorted(all_data, key=lambda x: x.get('time', ''), reverse=True)
    return sorted_data[:50] # Trả về tối đa 50 tin nhắn mới nhất

@app.get("/quickchats")
def get_quickchats():
    all_data = quickchat_db.all()
    # Bổ sung id để frontend có thể xóa
    for item in all_data:
        item['id'] = item.doc_id
    sorted_data = sorted(all_data, key=lambda x: x.get('time', ''), reverse=True)
    return sorted_data

@app.post("/quickchats")
def add_quickchat(request: QuickChatRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui lòng nhập Key")
    doc_id = quickchat_db.insert({
        'chinese': request.chinese,
        'vietnamese': request.vietnamese,
        'time': str(datetime.datetime.now())
    })
    return {"status": "success", "id": doc_id}

@app.delete("/quickchats/{doc_id}")
def delete_quickchat(doc_id: int, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui lòng nhập Key")
    quickchat_db.remove(doc_ids=[doc_id])
    return {"status": "success"}

# --- 3. Endpoint xử lý (Chèn vào trước đoạn if __name__ == "__main__") ---

@app.post("/capture_goofish")
def capture_goofish_ids(request: GoofishCaptureRequest):
    """
    Tự động parse ID từ payload Goofish và lưu vào TinyDB.
    Kiểm tra trùng lặp dựa trên product_id.
    """
    try:
        # 1. Truy cập vào ResultList (theo cấu trúc lồng nhau của Goofish)
        # data -> resultInfo -> searchResControlFields (chứa meta)
        # data -> resultList (chứa danh sách sản phẩm)
        result_list = request.payload.get("data", {}).get("resultList", [])
        
        new_ids_count = 0
        duplicate_count = 0
        extracted_ids = []

        for item in result_list:
            # Lấy ID theo path: data -> item -> main -> clickParam -> args -> id
            item_data = item.get("data", {})
            p_id = item_data.get("item", {}).get("main", {}).get("clickParam", {}).get("args", {}).get("id")
            
            if p_id:
                p_id_str = str(p_id) # Luôn lưu ở dạng chuỗi
                
                # 2. Kiểm tra trùng lặp trong TinyDB
                if not g_db.search(Product.product_id == p_id_str):
                    g_db.insert({
                        'product_id': p_id_str,
                        'captured_at': str(datetime.datetime.now())
                    })
                    new_ids_count += 1
                else:
                    duplicate_count += 1
                
                extracted_ids.append(p_id_str)

        return {
            "status": "success",
            "summary": {
                "total_in_payload": len(result_list),
                "new_added": new_ids_count,
                "duplicates_ignored": duplicate_count
            },
            "processed_ids": extracted_ids
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi parse Goofish: {str(e)}")

# Thêm endpoint GET để bạn kiểm tra danh sách ID đã lưu
@app.get("/goofish_products")
def get_goofish_products():
    return g_db.all()

# --- 3. Endpoint nhận dữ liệu từ Extension ---
@app.post("/capture_goofish_detail")
def capture_goofish_detail(payload: GoofishDetailPayload, x_api_key: str = Header(None)):
    try:
        # Lấy dữ liệu từ payload
        data_root = payload.data.get("data", {})
        item_do = data_root.get("itemDO", {})
        track_params = data_root.get("trackParams", {})
        
        # 1. Trích xuất ID (Luôn ưu tiên itemId định dạng chuỗi)
        product_id = str(item_do.get("itemId") or track_params.get("itemId"))
        
        if not product_id or product_id == "None":
            raise HTTPException(status_code=400, detail="Không tìm thấy ID sản phẩm")

        title = item_do.get("title")
        description = item_do.get("desc")

        # Dịch
        def translate_internal(text):
            if not text or not x_api_key: return text
            existing = xianyu_db.get(History.original == text)
            if existing: return existing['translated']
            try:
                payload_ai = {
                    "model": "gemini-3-flash",
                    "messages": [
                        {"role": "system", "content": "You are a specialized Vietnamese-Chinese translator. If input is Chinese, translate to Vietnamese. Return ONLY the translation."},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.2
                }
                response = requests.post(os.getenv("ANTIGRAVITY_URL", DEFAULT_ANTIGRAVITY_URL), json=payload_ai, headers={"Authorization": f"Bearer {x_api_key}"}, timeout=10)
                result = response.json()['choices'][0]['message']['content'].strip()
                xianyu_db.insert({'original': text, 'translated': result, 'count': 1, 'time': str(datetime.datetime.now())})
                return result
            except:
                return text

        translated_title = translate_internal(title)
        translated_desc = translate_internal(description)

        final_title = f"{translated_title}\n\n[Trung]: {title}" if title and translated_title and translated_title != title else title
        final_desc = f"{translated_desc}\n\n[Trung]: {description}" if description and translated_desc and translated_desc != description else description

        # 2. Xử lý bảng product_product (Lưu thông tin chính)
        product_info = {
            "product_id": product_id,
            "title": final_title,
            "price": item_do.get("soldPrice"),
            "status": item_do.get("itemStatusStr"),
            "city": data_root.get("sellerDO", {}).get("city"),
            "description": final_desc,
            "updated_at": str(datetime.datetime.now())
        }

        # Kiểm tra trùng lặp ID
        existing_prod = ProductTable.get(ProdQuery.product_id == product_id)
        if existing_prod:
            # CHỈ cập nhật thông tin máy, GIỮ NGUYÊN custom_tags cũ
            ProductTable.update(product_info, ProdQuery.product_id == product_id)
        else:
            # Nếu là sp mới hoàn toàn, khởi tạo mảng tag trống
            product_info["custom_tags"] = []
            ProductTable.insert(product_info)

        # 3. Xử lý bảng product_img (Chuyển ảnh vào bảng riêng)
        image_list = item_do.get("imageInfos", [])
        new_img_count = 0
        
        for img in image_list:
            img_url = img.get("url")
            # Kiểm tra trùng ảnh cho product này
            is_img_exist = ImageTable.get((ProdQuery.product_id == product_id) & (ProdQuery.url == img_url))
            
            if not is_img_exist:
                ImageTable.insert({
                    "product_id": product_id,
                    "url": img_url,
                    "width": img.get("widthSize"),
                    "height": img.get("heightSize"),
                    "captured_at": str(datetime.datetime.now())
                })
                new_img_count += 1

        return {
            "status": "success",
            "product_id": product_id,
            "new_images": new_img_count,
            "message": "Đã đồng bộ thông tin và hình ảnh"
        }

    except Exception as e:
        print(f"Error parsing detail: {e}")
        raise HTTPException(status_code=500, detail="Lỗi xử lý dữ liệu")

# 2. Thêm Endpoint quản lý Tags (Gán/Xóa tag)
@app.post("/product/update_tags")
def update_product_tags(request: TagUpdateRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Key required")
    
    existing = ProductTable.get(ProdQuery.product_id == request.product_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Sản phẩm chưa có trong DB")
    
    # Cập nhật mảng tag
    ProductTable.update({"custom_tags": request.tags}, ProdQuery.product_id == request.product_id)
    
    return {"status": "success", "updated_id": request.product_id, "current_tags": request.tags}

# 3. Endpoint Truy vấn (Lọc sản phẩm theo Tag)
@app.get("/products/by_tag/{tag_name}")
def get_products_by_tag(tag_name: str):
    # TinyDB hỗ trợ kiểm tra phần tử trong list bằng test()
    results = ProductTable.search(ProdQuery.custom_tags.test(lambda tags: tag_name in tags))
    return results

# 4. Lấy thông tin 1 sản phẩm (Cho extension hiển thị tag)
@app.get("/product/{product_id}")
def get_single_product(product_id: str):
    existing = ProductTable.get(ProdQuery.product_id == product_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Sản phẩm chưa có trong DB")
    
    # Lấy danh sách ảnh
    images = ImageTable.search(ProdQuery.product_id == product_id)
    existing["images"] = [img["url"] for img in images]
    
    return existing

# 5. Endpoints quản lý Cấu hình Tags (CRUD)
@app.get("/tags")
def get_tags():
    return TagTable.all()

@app.post("/tags")
def add_or_update_tag(tag: TagConfig, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Key required")
    existing = TagTable.get(TagQuery.name == tag.name)
    if existing:
        TagTable.update({"color": tag.color}, TagQuery.name == tag.name)
    else:
        TagTable.insert({"name": tag.name, "color": tag.color})
    return {"status": "success", "tag": tag.dict()}

@app.delete("/tags/{tag_name}")
def delete_tag(tag_name: str, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Key required")
    TagTable.remove(TagQuery.name == tag_name)
    return {"status": "success"}


@app.post("/chat_translate")
def chat_translate(request: ChatTranslateRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui long nhap Key")

    if not request.target_language or not request.target_language.strip():
        raise HTTPException(status_code=400, detail="target_language is required")

    if request.model is not None and not request.model.strip():
        raise HTTPException(status_code=400, detail="model must not be empty")

    selected_model = (request.model.strip() if request.model else None) or "gemini-3-flash"

    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    if not request.message_ids_to_translate:
        raise HTTPException(status_code=400, detail="message_ids_to_translate must not be empty")

    normalized_messages = []
    for message in request.messages:
        if not message.id.strip():
            raise HTTPException(status_code=400, detail="message id must not be empty")
        if not message.content.strip():
            raise HTTPException(status_code=400, detail="message content must not be empty")
        normalized_messages.append(
            {"id": message.id, "role": message.role.strip() or "role_a", "content": message.content}
        )

    try:
        context_messages = build_reduced_context_window(
            messages=normalized_messages,
            message_ids_to_translate=request.message_ids_to_translate,
            prior_limit=5,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    prompt = build_chat_translate_prompt(
        target_language=request.target_language.strip(),
        context_messages=context_messages,
        message_ids_to_translate=request.message_ids_to_translate,
        verify_back_translation=request.verify_back_translation,
    )

    antigravity_url = os.getenv(
        "ANTIGRAVITY_URL",
        DEFAULT_ANTIGRAVITY_URL,
    )

    payload = {
        "model": selected_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            antigravity_url,
            json=payload,
            headers={"Authorization": f"Bearer {x_api_key}"},
            timeout=90,
        )
        api_response = parse_chat_completion_response(response)
        if "choices" not in api_response:
            raise HTTPException(status_code=500, detail=f"Antigravity API Error: {api_response}")

        raw_content = api_response["choices"][0]["message"].get("content", "")
        parsed, fallback_text = parse_translation_payload(raw_content)

        if parsed is not None:
            results = parsed.get("results")

            if not isinstance(results, list):
                raise HTTPException(status_code=500, detail="Invalid translation response format")

            for item in results:
                if not isinstance(item, dict):
                    raise HTTPException(status_code=500, detail="Each translation result must be an object")
                if not item.get("id") or not item.get("translated_text") or not isinstance(item.get("translated_text"), str):
                    raise HTTPException(status_code=500, detail="Each translation result must include id and translated_text")
                back_translated = item.get("back_translated_text")
                if back_translated is None:
                    item["back_translated_text"] = ""
                elif not isinstance(back_translated, str):
                    raise HTTPException(status_code=500, detail="back_translated_text must be a string")
                else:
                    item["back_translated_text"] = back_translated

            returned_ids = {item["id"] for item in results}
            missing_ids = [message_id for message_id in request.message_ids_to_translate if message_id not in returned_ids]
            if missing_ids:
                raise HTTPException(status_code=500, detail=f"Missing translated ids: {missing_ids}")

            return {"results": results}
        else:
            results = [
                {
                    "id": message_id,
                    "translated_text": fallback_text,
                    "source_language": "",
                    "back_translated_text": "",
                }
                for message_id in request.message_ids_to_translate
            ]
            return {"results": results}
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI did not return valid JSON")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    # Sử dụng 0.0.0.0 để cho phép truy cập từ các thiết bị khác (Remote, Lan, v.v...)
    uvicorn.run(app, host="0.0.0.0", port=8000)

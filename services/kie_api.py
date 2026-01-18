"""
KIE.AI API連携（LINE Bot用・非同期版）
"""
import asyncio
import base64
import io
import json
import httpx
from PIL import Image

import asyncio
import base64
import io
import json
import httpx
from PIL import Image
from typing import Optional

from config import settings

# API URLs
CREATE_TASK_URL = "https://api.kie.ai/api/v1/jobs/createTask"
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-base64-upload"


def image_bytes_to_base64(image_bytes: bytes) -> str:
    """画像バイトをBase64文字列に変換"""
    image = Image.open(io.BytesIO(image_bytes))

    # リサイズ（大きすぎる場合）
    max_size = 1024
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # RGBA -> RGB
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGB")

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=90)
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_str}"


async def upload_image(base64_image: str) -> Optional[str]:
    """画像をKIE.AIにアップロード"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.KIEAI_API_KEY}"
    }
    payload = {
        "base64Data": base64_image,
        "filename": "upload.jpg",
        "uploadPath": "temp"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(UPLOAD_URL, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    return data["data"]["downloadUrl"]
        except Exception as e:
            print(f"Upload error: {e}")
    return None


async def get_webhook_token() -> Optional[str]:
    """Webhook.siteからトークン取得"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(3):
            try:
                res = await client.post("https://webhook.site/token")
                if res.status_code in [200, 201]:
                    return res.json()["uuid"]
            except Exception as e:
                print(f"Webhook token error (attempt {i+1}): {e}")
            await asyncio.sleep(1)
    return None


async def create_task(payload: dict) -> tuple[Optional[str], Optional[str]]:
    """KIE.AIタスク作成"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.KIEAI_API_KEY}"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(CREATE_TASK_URL, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 200:
                    return data["data"]["taskId"], None
                else:
                    return None, data.get("msg")
            else:
                return None, f"HTTP {res.status_code}"
        except Exception as e:
            return None, str(e)


async def poll_webhook(uuid: str, timeout: int = 120) -> Optional[str]:
    """Webhookをポーリングして結果URLを取得"""
    poll_url = f"https://webhook.site/token/{uuid}/requests"

    async with httpx.AsyncClient(timeout=10.0) as client:
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                res = await client.get(poll_url)
                if res.status_code == 200:
                    data_list = res.json().get("data", [])
                    for req in data_list:
                        content = req.get("content")
                        if content:
                            try:
                                body = json.loads(content)
                                data_body = body.get("data", {})
                                state = data_body.get("state")

                                if state == "success":
                                    if "resultUrls" in data_body and data_body["resultUrls"]:
                                        return data_body["resultUrls"][0]
                                    elif "resultJson" in data_body:
                                        rj = json.loads(data_body["resultJson"])
                                        if "resultUrls" in rj:
                                            return rj["resultUrls"][0]
                                elif state == "fail":
                                    return None
                            except:
                                pass
            except Exception as e:
                print(f"Polling error: {e}")

            await asyncio.sleep(3)

    return None


async def generate_parse(image_bytes: bytes, prompt: str) -> Optional[str]:
    """
    画像からパースを生成（メイン関数）

    Args:
        image_bytes: 画像のバイトデータ
        prompt: 生成プロンプト

    Returns:
        生成された画像のURL、失敗時はNone
    """
    try:
        # 1. 画像をBase64に変換
        base64_image = image_bytes_to_base64(image_bytes)

        # 2. 画像をアップロード
        image_url = await upload_image(base64_image)
        if not image_url:
            print("Image upload failed")
            return None

        # 3. Webhookトークン取得
        wh_uuid = await get_webhook_token()
        if not wh_uuid:
            print("Webhook token failed")
            return None

        callback_url = f"https://webhook.site/{wh_uuid}"

        # 4. タスク作成（Seedream 4.5 Editを使用 - 最も安定）
        task_payload = {
            "model": "seedream/4.5-edit",
            "callBackUrl": callback_url,
            "input": {
                "prompt": prompt,
                "image_urls": [image_url],
                "aspect_ratio": "16:9",
                "quality": "high"
            }
        }

        task_id, error = await create_task(task_payload)
        if not task_id:
            print(f"Task creation failed: {error}")
            return None

        # 5. 結果をポーリング
        result_url = await poll_webhook(wh_uuid, timeout=120)
        return result_url

    except Exception as e:
        print(f"Generation error: {e}")
        return None

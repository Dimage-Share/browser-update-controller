import os
import httpx
import logging

GCHAT_WEBHOOK = os.getenv("GCHAT_WEBHOOK", "")


async def chat_send(text: str):
    """
    Google Chat へのシンプルテキスト通知。
    Webhook が未設定の場合は何もしない。
    """
    if not GCHAT_WEBHOOK:
        return
    payload = {"text": text}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(GCHAT_WEBHOOK, json=payload)
            r.raise_for_status()
    except Exception as e:
        logging.warning(f"Google Chat send failed: {e}")


# （必要ならカード形式例）
# async def chat_send_card(title: str, body: str, color: str = "#3367d6"):
#     if not GCHAT_WEBHOOK: return
#     card = {
#       "cardsV2": [{
#         "cardId": "browser-update",
#         "card": {
#           "header": {"title": title},
#           "sections": [{
#             "widgets": [{
#               "textParagraph": {"text": body}
#             }]
#           }]
#         }
#       }]
#     }
#     try:
#       async with httpx.AsyncClient(timeout=10) as client:
#         await client.post(GCHAT_WEBHOOK, json=card)
#     except Exception as e:
#       logging.warning(f"Google Chat card failed: {e}")

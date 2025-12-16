async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import logging

logging.basicConfig(level=logging.INFO)
logging.info("Bot started successfully")
import os
import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp
from dotenv import load_dotenv

# ----------------------------------
# ENVIRONMENT
# ----------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🚨 ВАЖНО: по умолчанию используем PROD API
API_BASE = os.getenv(
    "API_BASE",
    "https://biginvest-api-production.up.railway.app"
)

API_TOKEN = os.getenv("API_TOKEN", "dev-token")
MANAGER_ID = os.getenv("MANAGER_ID", "mgr-001")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ----------------------------------
# API HELPERS
# ----------------------------------
async def api_get(session, path, params=None):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    async with session.get(f"{API_BASE}{path}", headers=headers, params=params) as r:
        r.raise_for_status()
        return await r.json()


async def api_post(session, path, payload):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    async with session.post(
        f"{API_BASE}{path}",
        headers=headers,
        data=json.dumps(payload)
    ) as r:
        r.raise_for_status()
        return await r.json()

# ----------------------------------
# UI HELPERS
# ----------------------------------
def action_kb(app_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить", callback_data=f"approve:{app_id}")
    kb.button(text="❌ Отклонить", callback_data=f"reject:{app_id}")
    kb.button(text="❓ Нужна инфо", callback_data=f"needinfo:{app_id}")
    kb.adjust(2, 1)
    return kb.as_markup()


def format_application(app: dict) -> str:
    lot = app.get("lot", {})
    customer = app.get("customer", {})

    tags = lot.get("tags", [])
    tag_string = ", ".join(tags) if tags else "—"

    return (
        f"🆕 Заявка #{app['id']}\n"
        f"Создана: {app.get('createdAt', '—')}\n"
        f"Статус: {app.get('status', 'NEW')}\n\n"
        f"👤 Клиент: {customer.get('name')} ({customer.get('phone')})\n"
        f"Способ связи: {app.get('contactMethod')}\n"
        f"Удобное время: {app.get('timeSlot')}\n"
        f"Комментарий: {app.get('comment', '—')}\n\n"
        f"🏢 Лот: {lot.get('title')}\n"
        f"Город: {lot.get('city')}\n"
        f"Блок: {lot.get('block')}\n"
        f"Цена: {lot.get('price')}\n"
        f"Теги: {tag_string}\n"
    )

# ----------------------------------
# BUSINESS LOGIC
# ----------------------------------
async def send_next_application(chat_id: int):
    async with aiohttp.ClientSession() as session:
        try:
            items = await api_get(session, "/applications/new")

            if not items:
                await bot.send_message(chat_id, "Новых заявок пока нет ✨")
                return

            app = items[0]

            await api_post(
                session,
                f"/applications/{app['id']}/status",
                {
                    "status": "IN_PROGRESS",
                    "managerId": MANAGER_ID,
                    "comment": None
                }
            )

            await bot.send_message(
                chat_id,
                format_application(app),
                reply_markup=action_kb(app["id"])
            )

        except Exception as e:
            await bot.send_message(chat_id, f"Ошибка при получении заявки: {e}")

# ----------------------------------
# HANDLERS
# ----------------------------------
@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        "Привет! Я бот для обработки заявок из BIG Invest.\n\n"
        "Доступные команды:\n"
        "• /next — взять следующую заявку"
    )


@dp.message(F.text == "/next")
async def next_cmd(m: types.Message):
    await send_next_application(m.chat.id)


@dp.callback_query(F.data.startswith(("approve:", "reject:", "needinfo:")))
async def handle_action(cq: types.CallbackQuery):
    try:
        action, app_id = cq.data.split(":")
        status_map = {
            "approve": "APPROVED",
            "reject": "REJECTED",
            "needinfo": "NEED_INFO"
        }

        async with aiohttp.ClientSession() as session:
            await api_post(
                session,
                f"/applications/{app_id}/status",
                {
                    "status": status_map[action],
                    "managerId": MANAGER_ID,
                    "comment": None
                }
            )

        await cq.message.edit_reply_markup(reply_markup=None)
        await cq.message.reply(
            f"Статус заявки #{app_id} → {status_map[action]}"
        )
        await cq.answer("Готово")

    except Exception as e:
        await cq.answer(f"Ошибка: {e}", show_alert=True)

# ----------------------------------
# MAIN
# ----------------------------------
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден")

    print("🤖 BIG Invest CRM Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

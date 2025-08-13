import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiohttp import web

# ---------- логирование ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

# ---------- ЧИТАЕМ ТОКЕН ТОЛЬКО ИЗ ОКРУЖЕНИЯ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # намеренно падаем, чтобы случайно не стартовать без секрета
    raise RuntimeError("Environment variable BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# ---------- /start ----------
@dp.message(commands=["start"])
async def start_handler(message: types.Message):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🛒 Купить аккаунт", callback_data="buy")],
        [types.InlineKeyboardButton(text="⭐ Отзывы", url="https://t.me/ВашКаналСОтзывами")],
        [types.InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/MeuzenFC")],
        [types.InlineKeyboardButton(text="📜 Правила / FAQ", url="https://t.me/ВашFAQилиПост")]
    ])
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=kb)

# пример «заглушки» на кнопку «Купить»
@dp.callback_query(lambda c: c.data == "buy")
async def buy_placeholder(cb: types.CallbackQuery):
    await cb.message.answer("Модуль покупки подключим позже. 🙂")
    await cb.answer()

# ---------- Render: удаляем вебхук и запускаем polling ----------
async def on_startup(app: web.Application):
    # снимаем любой активный webhook, чтобы не было конфликтов
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook removed, starting polling…")
    except Exception as e:
        logging.warning("Webhook delete failed: %s", e)

    app["polling_task"] = asyncio.create_task(dp.start_polling(bot))

async def on_shutdown(app: web.Application):
    task: asyncio.Task | None = app.get("polling_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await bot.session.close()
    logging.info("Bot stopped")

# маленький HTTP-сервер нужен Render’у (порт берём из $PORT)
async def health(_req: web.Request):
    return web.Response(text="ok")

def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/healthz", health)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))

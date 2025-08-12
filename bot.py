import os
import json
import asyncio
import logging
from decimal import Decimal, ROUND_HALF_UP

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, PhotoSize
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# -------------------- ЛОГИ --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# -------------------- НАСТРОЙКИ --------------------
BOT_TOKEN = "8217371794:AAHxN4QU5C6tj-8ynSwGnPUF7h-aC-HRWdg"

# ✅ Теперь можно несколько админов. Я добавил оба твоих ID.
ALLOWED_ADMIN_IDS = {906779125, 6074106582}

ADMIN_CHANNEL_ID = -1002632514549        # канал для подтверждений (копия также в ЛС админам)
SUPPORT_USERNAME = "MeuzenFC"

# --- ЦЕНЫ ---
CURRENCY = "₽"                            # "₽", "$", "€" и т.д.
PRICE_PER_ACCOUNT = Decimal("150.00")     # цена за 1 аккаунт

# --- РЕКВИЗИТЫ ДЛЯ ПЕРЕВОДА НА КАРТУ ---
CARD_NUMBER = "5559 4931 2345 6789"
CARD_HOLDER = "IVAN IVANOV"
CARD_NOTE   = "TGACC"   # комментарий к переводу (если не нужен — "")

# -------------------- ИНИЦ --------------------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

STOCK_FILE = "stock.json"
if not os.path.exists(STOCK_FILE):
    with open(STOCK_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

def load_stock():
    with open(STOCK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stock(stock):
    with open(STOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(stock, f, ensure_ascii=False, indent=2)

def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Купить аккаунт", callback_data="buy")
    kb.button(text="⭐ Отзывы", callback_data="reviews")
    kb.button(text="💬 Поддержка", callback_data="support")
    kb.adjust(1)
    return kb.as_markup()

# -------------------- ХЕЛПЕРЫ --------------------
def parse_account_line(line: str):
    # строго: login:password:+phone
    if not line:
        return None
    parts = [p.strip() for p in line.split(":")]
    if len(parts) != 3:
        return None
    login, password, phone = parts
    if not (login and password and phone and phone.startswith("+")):
        return None
    return {"login": login, "password": password, "phone": phone}

def format_account_message(acc_line: str) -> str:
    p = parse_account_line(acc_line)
    if not p:
        return f"<b>Ваш аккаунт Telegram</b>\n<code>{acc_line}</code>\n\nЕсли не удаётся войти — напишите: @{SUPPORT_USERNAME}"
    return (
        "<b>Ваш аккаунт Telegram</b>\n"
        f"<b>Логин:</b> <code>{p['login']}</code>\n"
        f"<b>Пароль:</b> <code>{p['password']}</code>\n"
        f"<b>Телефон:</b> <code>{p['phone']}</code>"
    )

def format_accounts_block(lines: list[str]) -> str:
    return "\n".join(f"{i}. <code>{line}</code>" for i, line in enumerate(lines, 1))

def money(x: Decimal) -> str:
    x = x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{x:.2f}"
    if s.endswith(".00"):
        s = s[:-3]
    return f"{s} {CURRENCY}"

async def is_admin_user(user_id: int) -> bool:
    """разрешаем нажатие, если пользователь в ALLOWED_ADMIN_IDS или админ канала"""
    if user_id in ALLOWED_ADMIN_IDS:
        return True
    try:
        cm = await bot.get_chat_member(ADMIN_CHANNEL_ID, user_id)
        return cm.status in ("administrator", "creator")
    except Exception:
        return False

# --- Память сессии ---
WAIT_CONTACT = set()               # ждём контакт после "Купить"
USER_LAST_CONTACT: dict[int, str] = {}
AWAIT_PROOF: set[int] = set()      # ждём скриншот оплаты
PAYMENT_PROOF: dict[int, str] = {} # file_id фото-чека
USER_QTY: dict[int, int] = {}      # выбранное кол-во (1..100)

# -------------------- КЛАВИАТУРЫ --------------------
def qty_kb(uid: int) -> InlineKeyboardMarkup:
    q = USER_QTY.get(uid, 1)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="−", callback_data="qty:dec"),
            InlineKeyboardButton(text=f"{q}", callback_data="qty:no"),
            InlineKeyboardButton(text="+", callback_data="qty:inc"),
        ],
        [InlineKeyboardButton(text="➡️ Далее", callback_data="qty:next")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="pay:back")]
    ])

def paid_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="paid:confirm")],
        [InlineKeyboardButton(text="↩️ Ввести контакт заново", callback_data="pay:back")]
    ])

def admin_decision_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{uid}")],
        [InlineKeyboardButton(text="🚫 Отклонить",   callback_data=f"reject:{uid}")]
    ])

# -------------------- ХЕНДЛЕРЫ --------------------
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=main_menu())

@dp.message(Command("whoami"))
async def whoami(message: Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>")

@dp.callback_query(F.data == "support")
async def support(cb: CallbackQuery):
    await cb.message.answer(f"По всем вопросам: @{SUPPORT_USERNAME}")
    await cb.answer()

@dp.callback_query(F.data == "reviews")
async def reviews(cb: CallbackQuery):
    await cb.message.answer("Отзывы: ⭐⭐⭐⭐⭐ Всё супер! Спасибо за покупку!")
    await cb.answer()

@dp.callback_query(F.data == "buy")
async def buy(cb: CallbackQuery):
    WAIT_CONTACT.add(cb.from_user.id)
    await cb.message.answer(
        "Отправьте ваш @username или ссылку для связи.\n"
        "После этого выберите количество, пришлите скрин перевода и нажмите «Я оплатил(а)».\n"
        "Отменить: /cancel"
    )
    await cb.answer()

@dp.message(Command("cancel"))
async def cancel(message: Message):
    WAIT_CONTACT.discard(message.from_user.id)
    AWAIT_PROOF.discard(message.from_user.id)
    PAYMENT_PROOF.pop(message.from_user.id, None)
    USER_QTY.pop(message.from_user.id, None)
    await message.answer("Отменено.", reply_markup=main_menu())

@dp.callback_query(F.data == "pay:back")
async def pay_back(cb: CallbackQuery):
    WAIT_CONTACT.add(cb.from_user.id)
    AWAIT_PROOF.discard(cb.from_user.id)
    PAYMENT_PROOF.pop(cb.from_user.id, None)
    USER_QTY.pop(cb.from_user.id, None)
    await cb.message.answer("Отправьте ваш @username или ссылку для связи.\nОтменить: /cancel")
    await cb.answer()

@dp.message()
async def collect_contact_or_proof(message: Message):
    uid = message.from_user.id

    # 1) Принимаем скриншот оплаты (фото)
    if uid in AWAIT_PROOF and message.photo:
        best: PhotoSize = max(message.photo, key=lambda p: p.width * p.height)
        PAYMENT_PROOF[uid] = best.file_id
        await message.reply("✅ Скриншот оплаты получен. Теперь нажмите «Я оплатил(а)».", reply_markup=paid_confirm_kb())
        return

    # 2) Принимаем контакт → затем выбор количества
    if uid in WAIT_CONTACT:
        WAIT_CONTACT.discard(uid)
        contact = (message.text or "").strip()
        if not contact:
            await message.answer("Пусто. Введите @username или ссылку.")
            WAIT_CONTACT.add(uid)
            return

        USER_LAST_CONTACT[uid] = contact
        USER_QTY[uid] = 1  # по умолчанию 1
        q = USER_QTY[uid]
        price = PRICE_PER_ACCOUNT
        total = (price * q)
        await message.answer(
            "Выберите количество аккаунтов (1–100):\n"
            f"Цена за 1: <b>{money(price)}</b>\n"
            f"Итого за {q}: <b>{money(total)}</b>",
            reply_markup=qty_kb(uid)
        )
        return

    # Иное — игнор
    return

# -------- Выбор количества --------
@dp.callback_query(F.data.in_(["qty:inc", "qty:dec", "qty:next", "qty:no"]))
async def qty_handlers(cb: CallbackQuery):
    uid = cb.from_user.id
    q = USER_QTY.get(uid, 1)

    updated = False
    if cb.data == "qty:inc":
        q = min(100, q + 1); updated = True
    elif cb.data == "qty:dec":
        q = max(1, q - 1);   updated = True

    if updated:
        USER_QTY[uid] = q
        price = PRICE_PER_ACCOUNT
        total = price * q
        try:
            await cb.message.edit_text(
                "Выберите количество аккаунтов (1–100):\n"
                f"Цена за 1: <b>{money(price)}</b>\n"
                f"Итого за {q}: <b>{money(total)}</b>",
                reply_markup=qty_kb(uid)
            )
        except TelegramBadRequest:
            await cb.message.edit_reply_markup(reply_markup=qty_kb(uid))
        await cb.answer()
        return

    if cb.data == "qty:no":
        await cb.answer(); return

    if cb.data == "qty:next":
        AWAIT_PROOF.add(uid)
        PAYMENT_PROOF.pop(uid, None)
        q = USER_QTY.get(uid, 1)
        price = PRICE_PER_ACCOUNT
        total = price * q
        text = (
            "🪙 <b>Перевод на карту</b>\n"
            f"<b>Номер:</b> <code>{CARD_NUMBER}</code>\n"
            f"<b>Получатель:</b> {CARD_HOLDER}\n"
            + (f"<b>Комментарий к переводу:</b> <code>{CARD_NOTE}</code>\n" if CARD_NOTE else "") +
            f"\n<b>Количество:</b> {q} шт.\n"
            f"<b>Итого к оплате:</b> {money(total)}\n"
            "После перевода отправьте сюда <b>скриншот оплаты</b>, затем нажмите кнопку ниже."
        )
        await cb.message.answer(text, reply_markup=paid_confirm_kb())
        await cb.answer(); return

# -------- Отправка карточки оплаты админу --------
@dp.callback_query(F.data == "paid:confirm")
async def paid_confirm(cb: CallbackQuery):
    uid = cb.from_user.id
    contact = USER_LAST_CONTACT.get(uid, "(не указан)")
    proof_id = PAYMENT_PROOF.get(uid)
    q = USER_QTY.get(uid, 1)
    price = PRICE_PER_ACCOUNT
    total = price * q

    if uid in AWAIT_PROOF and not proof_id:
        await cb.answer("Прикрепите скрин оплаты сообщением и снова нажмите кнопку.", show_alert=True)
        return

    caption = (
        "🆕 <b>Заявка об оплате</b>\n"
        f"<b>Покупатель:</b> tg://user?id={uid}\n"
        f"<b>Контакт:</b> {contact}\n"
        f"<b>Количество:</b> {q} шт.\n"
        f"<b>Цена за 1:</b> {money(price)}\n"
        f"<b>Итого оплачено:</b> {money(total)}\n"
        "<b>Статус:</b> пользователь нажал «Я оплатил(а)»"
    )

    # Карточка одним сообщением (фото + подпись + кнопки)
    # 1) Канал
    try:
        await bot.send_photo(
            ADMIN_CHANNEL_ID,
            photo=proof_id,
            caption=caption,
            reply_markup=admin_decision_kb(uid)
        )
        logging.info("Paid card sent to channel")
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logging.warning("Channel send failed (paid card): %s", e)
    except Exception as e:
        logging.exception("Channel error (paid card): %s", e)

    # 2) ЛС всем админам из списка
    for admin_id in ALLOWED_ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo=proof_id,
                caption=caption + "\n\n(копия для админа)",
                reply_markup=admin_decision_kb(uid)
            )
            logging.info("Paid card sent to admin DM %s", admin_id)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logging.warning("DM send failed (paid card) to %s: %s", admin_id, e)
        except Exception as e:
            logging.exception("DM error (paid card) to %s: %s", admin_id, e)

    AWAIT_PROOF.discard(uid)
    await cb.message.answer("Спасибо! Мы проверим оплату и подтвердим заказ.")
    await cb.answer()

# -------- Подтверждение/отклонение --------
@dp.callback_query(F.data.startswith("approve:"))
async def approve(cb: CallbackQuery):
    if not (await is_admin_user(cb.from_user.id)):
        await cb.answer("Нет доступа", show_alert=True); return

    user_id = int(cb.data.split(":")[1])
    qty = USER_QTY.get(user_id, 1)

    stock = load_stock()
    if len(stock) < qty:
        await cb.message.answer(f"⚠️ Недостаточно на складе: есть {len(stock)}, нужно {qty}. Пополните stock.json.")
        await cb.answer("Не хватает", show_alert=True)
        return

    to_send = stock[:qty]
    rest = stock[qty:]
    save_stock(rest)

    total = PRICE_PER_ACCOUNT * qty
    header = "<b>Ваш аккаунт Telegram</b>\n" if qty == 1 else f"<b>Ваши аккаунты Telegram ({qty} шт.)</b>\n"
    body = format_accounts_block(to_send)
    footer = f"\n\n<b>Оплачено:</b> {money(total)}"
    msg = header + body + footer

    try:
        await bot.send_message(user_id, msg)
        await cb.message.answer(f"✅ Подтверждено. Выдано {qty} шт.")
        await cb.answer("Отправлено")
    except TelegramForbiddenError:
        await cb.message.answer("⚠️ Не удалось отправить ЛС пользователю (возможно, он не писал боту).")
        await cb.answer("Ошибка", show_alert=True)
    except Exception as e:
        logging.exception("Delivery error: %s", e)
        await cb.message.answer(f"Ошибка отправки аккаунтов: {e}")
        await cb.answer("Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("reject:"))
async def reject(cb: CallbackQuery):
    if not (await is_admin_user(cb.from_user.id)):
        await cb.answer("Нет доступа", show_alert=True); return
    user_id = int(cb.data.split(":")[1])
    try:
        await bot.send_message(user_id, "Ваш заказ отклонён. Обратитесь в поддержку.")
    except Exception:
        pass
    await cb.message.answer("Отклонено.")
    await cb.answer("Ок")

# -------------------- ЗАПУСК --------------------
async def main():
    print("Bot started. Waiting for updates…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

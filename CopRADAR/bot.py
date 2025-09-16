import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, InputFile, BufferedInputFile, CallbackQuery
from config import BOT_TOKEN, CHANNEL_ID, HELP_CHAT_LINK 
from captcha import generate_captcha
from aiogram.client.default import DefaultBotProperties
from db import add_user, get_user, update_user
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import io
from datetime import datetime
from zoneinfo import ZoneInfo

CHID = CHANNEL_ID
###CHAT_LINK = LINKCHAT
tz = ZoneInfo("Asia/Kolkata")



# 🏅 Ранги (RU / EN / )
RANKS = [
    {"min_points": 0,   "ru": "👶 Новичок", "en": "👶 Beginner"},
    {"min_points": 100, "ru": "🕵️ Скаут",  "en": "🕵️ Scout"},
    {"min_points": 300, "ru": "👁️ Наблюдающий", "en": "👁️ Observer"},
    {"min_points": 500, "ru": "🧐 Смотрящий", "en": "🧐 Watcher"},
    {"min_points": 800, "ru": "🦅 Глаз Системы", "en": "🦅 Eye of the System"}
]

def get_rank(points: float) -> dict:
    """
    Возвращает ранг (словарь со всеми языками)
    """
    rank = RANKS[0]
    for r in RANKS:
        if points >= r['min_points']:
            rank = r
    return rank

def update_user_activity(user_id, added_points: float):
    user = get_user(user_id)
    new_points = user.get('points', 0) + added_points
    new_rank = get_rank(new_points)

    update_user(user_id, points=new_points, rank=new_rank)  # теперь rank — словарь

    return new_rank, new_points


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()


captcha_codes = {}

langs = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}

def main_menu(lang: str = "ru"):
    if lang == "ru":
        buttons = [
            ("📍 Мост/Круг - Чисто", "bridge_clear"),
            ("🚔 Мост/Круг - Копы", "bridge_cops"),
            ("🚨 Отметить копов", "report_cops"),
            ("✅ Копов нет", "no_cops"),
            ("🆘 Нужна помощь", HELP_CHAT_LINK)  # редирект
        ]
    elif lang == "en":
        buttons = [
            ("📍 Bridge/Circle - Clear", "bridge_clear"),
            ("🚔 Bridge/Circle - Cops", "bridge_cops"),
            ("🚨 Report Cops", "report_cops"),
            ("✅ No Cops", "no_cops"),
            ("🆘 Need Help", HELP_CHAT_LINK)  # редирект
        ]
    else:
        buttons = [
            ("📍 Bridge/Circle - Clear", "bridge_clear"),
            ("🚔 Bridge/Circle - Cops", "bridge_cops"),
            ("🚨 Report Cops", "report_cops"),
            ("✅ No Cops", "no_cops"),
            ("🆘 Need Help", HELP_CHAT_LINK)
        ]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    url=callback if text.startswith("🆘") else None,
                    callback_data=None if text.startswith("🆘") else callback
                )
            ]
            for text, callback in buttons
        ]
    )
    return kb

@dp.message(F.text == "/start")
async def start_cmd(message: Message):
    add_user(message.from_user.id)
    user = get_user(message.from_user.id)

    if user['lang'] is None or user['lang'] == "":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=langs["ru"], callback_data="lang_ru")],
                [InlineKeyboardButton(text=langs["en"], callback_data="lang_en")]
            ]
        )
        await message.answer("👋 Привет! Выбери язык / Choose language", reply_markup=kb)
        return

    # Если язык уже выбран, идём сразу к капче
    if not user['verifed']:
        await start_captcha(message.from_user.id)
    else:
        await send_welcome(message, user)



@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    update_user(callback.from_user.id, lang=lang_code)
    await callback.answer("✅ Язык выбран")
    await callback.message.delete()

    # Теперь капча стартует сразу
    await start_captcha(callback.from_user.id)









# -----------------------------
# Функция запуска капчи
# -----------------------------
# -----------------------------
# Функция запуска капчи
# -----------------------------
async def start_captcha(chat_id: int):
    user = get_user(chat_id)

    if user.get('verifed', False):
        await send_welcome(chat_id)
        return

    code, img = generate_captcha()
    captcha_codes[chat_id] = code

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    lang = user.get('lang', 'en')
    text = {
        "ru": "🛡 Для входа реши капчу. Введи число с картинки:",
        "en": "🛡 Solve the captcha to enter. Enter the number from the image:"
    }.get(lang, "🛡 Solve the captcha to enter.")

    await bot.send_message(chat_id, text)
    await bot.send_photo(chat_id, BufferedInputFile(buf.read(), filename="captcha.png"))



# -----------------------------
# Проверка капчи
# -----------------------------
@dp.message(F.text.regexp(r"^\d{4}$"))
async def check_captcha(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await message.answer("⚠ Ошибка. Сначала отправь /start")
        return

    # Если пользователь уже верифицирован → ничего не делаем
    if user.get('verifed', False):
        captcha_codes.pop(user_id, None)  # удаляем капчу на всякий случай
        return

    # Если капча отсутствует → создаём новую
    if user_id not in captcha_codes:
        await start_captcha(message)
        return

    # Проверяем код
    if message.text == captcha_codes[user_id]:
        # Верно
        update_user(user_id, verifed=True)
        captcha_codes.pop(user_id, None)

        # Загружаем свежие данные из БД
        user = get_user(user_id)
        await send_welcome(message, user)
    else:
        # Неверно → новая капча
        code, img = generate_captcha()
        captcha_codes[user_id] = code

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        lang = user.get('lang', 'en')
        text = {
            "ru": "❌ Неверно! Новая капча. Введи число с картинки:",
            "en": "❌ Wrong! New captcha. Enter the number from the image:"
        }.get(lang, "❌ Wrong! New captcha. Enter the number from the image:")

        await message.answer(text)
        await message.answer_photo(photo=BufferedInputFile(buf.read(), filename="captcha.png"))

# Приветствие на выбранном языке
from aiogram.types import FSInputFile

async def send_welcome(message: Message, user):
    lang = user['lang']

    # Локальный файл как FSInputFile
    photo = FSInputFile("welcome.jpg")

    if lang == "ru":
        welcome_text = (
            "👋 Добро пожаловать в <b>CopRadar</b>!\n"
            "🗺 Твоя анонимная карта наблюдения.\n\n"
            "Здесь ты можешь:\n"
            "📍 Мгновенно отмечать посты полиции\n"
            "📰 Получать актуальную информацию от других наблюдателей\n"
            "🆘 Попросить помощи у других участников чата\n\n"
            "Все анонимно 🕶️.\n\n"
            "Чем больше ты помогаешь — тем выше твой рейтинг ⭐ и звание:\n"
            "👶 Новичок\n🕵️ Скаут\n👁️ Наблюдающий\n🧐 Смотрящий\n🦅 Глаз Системы"
        )
    elif lang == "en":
        welcome_text = (
            "👋 Welcome to <b>CopRadar</b>!\n"
            "🗺 Your anonymous observation map.\n\n"
            "Here you can:\n"
            "📍 Instantly mark police posts\n"
            "📰 Get current info from other observers\n"
            "🆘 Request help from other participants\n\n"
            "All anonymous 🕶️.\n\n"
            "The more you help — the higher your rating ⭐ and rank:\n"
            "👶 Beginner\n🕵️ Scout\n👁️ Observer\n🧐 Watcher\n🦅 Eye of the System"
        )

    await message.answer_photo(
        photo=photo,
        caption=welcome_text,
        reply_markup=main_menu(user['lang']),
        parse_mode="HTML"
    )


@dp.message(F.text.in_([langs["ru"], langs['en']]))
async def set_lang(message: Message):
    lang_code = [k for k, v in langs.items() if v == message.text][0]
    update_user(message.from_user.id, lang=lang_code)
    user = get_user(message.from_user.id)  # Получаем актуальные данные после обновления
    await message.answer(f"✅ Язык сохранён: {message.text}", reply_markup=main_menu(user['lang']))





 
# Тексты для кнопки "Чисто"
clear_buttons = {
    "📍 Мост/Круг - Чисто": "ru",
    "📍 Bridge/Circle - Clear": "en",
}

clear_texts = {
    "ru": "Копов нет, дорога свободна ✅",
    "en": "No cops, the road is clear ✅",
}

@dp.callback_query(F.data == "bridge_clear")
async def bridge_clear(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    lang_pressed = "ru" if user['lang'] == "ru" else "en"  # выбираем язык для ответа

    # Начисляем очки и обновляем ранг
    new_rank, new_points = update_user_activity(user_id, added_points=10)
    current_rank = f"{new_rank['ru']} / {new_rank['en']}  ({new_points:.0f} очков)"

    timestamp = datetime.now(tz).strftime("%H:%M:%S")
    lat, lon = 15.64090, 73.75887

    # Отправка гео в канал
    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)

    # Сообщение в канал
    msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{clear_texts['ru']}\n"
        f"{clear_texts['en']}\n"
        f"📍 Координаты: {lat}, {lon}"
    )
    await bot.send_message(chat_id=CHID, text=msg)

    # Ответ пользователю
    await callback.message.answer(
        f"✅ Отметка отправлена: {clear_texts[lang_pressed]}\n"
        f"🎖 Твой текущий ранг:\n{current_rank}",
        parse_mode="HTML"
    )

    # Обновляем рейтинг
    user = get_user(user_id)
    new_rating = min(user['rating'] + 0.2, 5)
    update_user(user_id, rating=new_rating)

    await callback.answer()  # закрываем "часики" в кнопке




cops_buttons = {
    "🚔 Мост/Круг - Копы": "ru",
    "🚔 Bridge/Circle - Cops": "en",
}

cops_texts = {
    "ru": "Замечены копы 🚔",
    "en": "Cops spotted 🚔",
}


@dp.callback_query(F.data == "bridge_cops")
async def bridge_cops(callback : CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    lang_pressed = 'ru' if user['lang'] == 'ru' else 'en'

    # Добавляем очки активности и получаем обновлённый ранг и очки
    new_rank, new_points = update_user_activity(user_id, added_points=10)

    # Формируем читабельную строку ранга
    current_rank = f"{new_rank['ru']} / {new_rank['en']} ({new_points:.0f} очков)"

    timestamp = datetime.now(tz).strftime("%H:%M:%S")
    lat, lon = 15.64090, 73.75887

    # Отправка гео в канал
    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)

    # Сообщение в канал с уже форматированным ранговым текстом
    channel_msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{cops_texts['ru']}\n"
        f"{cops_texts['en']}\n"
        f"📍 Координаты: {lat}, {lon}"
    )
    await bot.send_message(chat_id=CHID, text=channel_msg, parse_mode="HTML")

    # Сообщение пользователю — отметка и ранг
    await callback.message.answer(
        f"✅ Отметка отправлена: {cops_texts[lang_pressed]}\n"
        f"🎖 Твой текущий ранг:\n{current_rank}",
        parse_mode="HTML"
    )

    # Обновляем рейтинг
    user = get_user(user_id)
    new_rating = min(user['rating'] + 0.2, 5)
    update_user(user_id, rating=new_rating)


 # Тексты для кнопки "Отметить копов"
report_buttons = {
    "🚨 Отметить копов": "ru",
    "🚨 Report Cops": "en",
}

report_texts = {
    "ru": "Замечены копы 🚔",
    "en": "Cops reported 🚔",
}

class ReportCops(StatesGroup):
    waiting_for_location = State()


@dp.callback_query(F.data == "report_cops")
async def report_cops_request(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id     )
    lang_pressed = 'ru' if user['lang'] == 'ru' else 'en'
    await state.set_state(ReportCops.waiting_for_location)  # ждем гео
    await state.update_data(lang_pressed=lang_pressed)  # сохраним язык

    if lang_pressed == "ru":
        await callback.message.answer("📍 Отправь гео-метку места, где находятся копы. \nЧто бы отправить гео-метку, нажмите на скрепку в левом нижнем углу и выберите 'Геопозиция' ")
    elif lang_pressed == "en":
        await callback.message.answer("📍📍 Send the location of where the cops are.\nTo send a location, tap the paperclip in the lower-left corner and select 'Location'.")

    await callback.answer()

@dp.message(ReportCops.waiting_for_location, F.location)
async def report_cops_location(message: Message, state : FSMContext):
    data = await state.get_data()
    lang_pressed = data['lang_pressed']
    user_id = message.from_user.id

    new_rank, new_points = update_user_activity(user_id, added_points=10)

    # Формируем читабельную строку ранга
    current_rank = f"{new_rank['ru']} / {new_rank['en']} ({new_points:.0f} очков)"

    user = get_user(message.from_user.id)
    lat, lon = message.location.latitude, message.location.longitude
    timestamp = datetime.now(tz).strftime("%H:%M:%S")


    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)
    msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{report_texts['ru']}\n"
        f"{report_texts['en']}\n"
        f"📍 Координаты: {lat}, {lon}"
    )
    await bot.send_message(chat_id=CHID, text=msg)

    await message.answer(
        f"✅ {report_texts[lang_pressed]} — координаты отправлены!\n"
        f"🎖 Твой текущий ранг:\n{current_rank}",
        parse_mode="HTML"
    )

    user = get_user(user_id)
    new_rating = min(user['rating'] + 0.2, 5)
    update_user(user_id, rating=new_rating)

    await state.clear()


nocops_buttons = {
    "✅ Копов нет": "ru",
    "✅ No Cops": "en",
}

nocops_texts = {
    "ru": "Копов нет, дорога свободна ✅",
    "en": "No cops, the road is clear ✅",
}


# FSM для ожидания гео
class NoCops(StatesGroup):
    waiting_for_location = State()


# Обработка кнопки
@dp.callback_query(F.data == 'no_cops')
async def nocops_request(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)
    lang_pressed = 'ru' if user['lang'] == 'ru' else 'en'
    await state.set_state(NoCops.waiting_for_location)   # ждем гео
    await state.update_data(lang_pressed=lang_pressed)   # сохраняем язык

    prompts = {
        "ru": "📍 Отправь гео-метку места, где копов НЕТ. \nЧто бы отправить гео-метку, нажмите на скрепку в левом нижнем углу и выберите 'Геопозиция'",
        "en": "📍 Send the location where there are NO cops.\nTo send a location, tap the paperclip in the lower-left corner and select 'Location'.",
    }
    await callback.message.answer(prompts[lang_pressed])


# Обработка гео-метки
@dp.message(NoCops.waiting_for_location, F.location)
async def nocops_location(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_pressed = data["lang_pressed"]
    user_id = message.from_user.id

    user = get_user(message.from_user.id)
    lat, lon = message.location.latitude, message.location.longitude
    timestamp = datetime.now(tz).strftime("%H:%M:%S")

    new_rank, new_points = update_user_activity(user_id, added_points=10)

    # Формируем читабельную строку ранга
    current_rank = f"{new_rank['ru']} / {new_rank['en']} ({new_points:.0f} очков)"

    # Отправляем гео в канал
    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)

    # Сообщение в канал на 3 языках
    msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{nocops_texts['ru']}\n"
        f"{nocops_texts['en']}\n"
        f"📍 Координаты: {lat}, {lon}"
    )
    await bot.send_message(chat_id=CHID, text=msg)

    # Ответ пользователю на его языке
    await message.answer(
        f"✅ {nocops_texts[lang_pressed]} — координаты отправлены!\n"
        f"🎖 Твой текущий ранг:\n{current_rank}",
        parse_mode="HTML"
    )

    # Обновляем рейтинг
    user = get_user(user_id)
    new_rating = min(user['rating'] + 0.2, 5)
    update_user(user_id, rating=new_rating)

    await state.clear()


help_buttons = {
    "🆘 Нужна помощь": "ru",
    "🆘 Need Help": "en",
}

help_texts = {
    "ru": "Если нужна помощь — заходи в чат:",
    "en": "If you need help — join the chat:",
}

CHAT_ID = "none"


@dp.callback_query(F.data == 'need_help')
async def need_help(callback : CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    lang_pressed = 'ru' if user['lang'] == 'ru' else 'en'

    try:
        # Создаём временную ссылку (1 день)
        invite = await bot.create_chat_invite_link(
            chat_id=CHAT_ID,
            expire_date=int(datetime.now().timestamp()) + 86400,
            name=f"invite_for_{callback.from_user.id}"
        )

        await callback.message.answer(
            f"{help_texts[lang_pressed]}\n👉 {invite.invite_link}"
        )

    except Exception as e:
        # если бот не админ или нет прав
        await callback.message.answer(
            f"{help_texts[lang_pressed]}\n⚠️ Ошибка: бот не может создать приглашение."
        )
        print(f"Error creating invite link: {e}")



async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

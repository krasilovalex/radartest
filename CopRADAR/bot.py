import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InputFile
from config import BOT_TOKEN, CHANNEL_ID
from captcha import generate_captcha
from aiogram.client.default import DefaultBotProperties
from db import add_user, get_user, update_user
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import io
from datetime import datetime

CHID = CHANNEL_ID



# 🏅 Ранги (RU / EN / HI)
RANKS = [
    {"min_points": 0,   "ru": "👶 Новичок", "en": "👶 Beginner", "hi": "👶 नया"},
    {"min_points": 100, "ru": "🕵️ Скаут",  "en": "🕵️ Scout",    "hi": "🕵️ टोही"},
    {"min_points": 300, "ru": "👁️ Наблюдающий", "en": "👁️ Observer", "hi": "👁️ पर्यवेक्षक"},
    {"min_points": 500, "ru": "🧐 Смотрящий", "en": "🧐 Watcher",  "hi": "🧐 चौकसी"},
    {"min_points": 800, "ru": "🦅 Глаз Системы", "en": "🦅 Eye of the System", "hi": "🦅 प्रणाली की आंख"}
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
    "hi": "🇮🇳 हिंदी"
}

def main_menu(lang: str = "ru"):
    if lang == "ru":
        buttons = [
            ["📍 Мост/Круг - Чисто"],
            ["🚔 Мост/Круг - Копы"],
            ["🚨 Отметить копов"],
            ["✅ Копов нет"],
            ["🆘 Нужна помощь"]
        ]
    elif lang == "en":
        buttons = [
            ["📍 Bridge/Circle - Clear"],
            ["🚔 Bridge/Circle - Cops"],
            ["🚨 Report Cops"],
            ["✅ No Cops"],
            ["🆘 Need Help"]
        ]
    elif lang == "hi":
        buttons = [
            ["📍 पुल/वृत्त - साफ़"],
            ["🚔 पुल/वृत्त - पुलिस"],
            ["🚨 पुलिस रिपोर्ट करें"],
            ["✅ पुलिस नहीं"],
            ["🆘 मदद चाहिए"]
        ]
    else:
        buttons = [
            ["📍 Bridge/Circle - Clear"],
            ["🚔 Bridge/Circle - Cops"],
            ["🚨 Report Cops"],
            ["✅ No Cops"],
            ["🆘 Need Help"]
        ]

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b[0]) for b in [row]] for row in buttons],
        resize_keyboard=True
    )
    return kb



@dp.message(F.text == "/start")
async def start_cmd(message: Message):
    add_user(message.from_user.id)
    user = get_user(message.from_user.id)

    if user['lang'] is None or user['lang'] == "":
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=langs["ru"])],
                [KeyboardButton(text=langs["en"])],
                [KeyboardButton(text=langs["hi"])]
            ],
            resize_keyboard=True
        )
        await message.answer("👋 Привет! Выбери язык / Choose language / भाषा चुनें:", reply_markup=kb)
        return  # важно: прекращаем выполнение здесь

    # Если язык уже выбран, идём сразу к капче
    if not user['verifed']:
        await start_captcha(message, user)
    else:
        await send_welcome(message, user)


# Обработка выбора языка
@dp.message(F.text.in_([langs["ru"], langs['en'], langs['hi']]))
async def set_lang(message: Message):
    lang_code = [k for k, v in langs.items() if v == message.text][0]
    update_user(message.from_user.id, lang=lang_code)
    user = get_user(message.from_user.id)

    # После выбора языка — запускаем капчу
    await start_captcha(message, user)




# Функция капчи
async def start_captcha(message: Message, user):
    # Если пользователь ещё не верифицирован
    if not user['verifed']:
        code, img = generate_captcha()
        captcha_codes[message.from_user.id] = code

        temp_file = "captcha.png"
        img.save(temp_file)

        # Подпись капчи на языке пользователя
        lang = user['lang']
        if lang == "ru":
            text = "🛡 Для входа реши капчу. Введи число с картинки:"
        elif lang == "en":
            text = "🛡 Solve the captcha to enter. Enter the number from the image:"
        elif lang == "hi":
            text = "🛡 प्रवेश के लिए कैप्चा हल करें। चित्र से संख्या दर्ज करें:"
        else:
            text = "🛡 Solve the captcha to enter."

        await message.answer(text)
        await bot.send_photo(chat_id=message.chat.id, photo=FSInputFile(temp_file))

    else:
        # Если уже верифицирован — приветствие
        await send_welcome(message, user)

# Проверка капчи
@dp.message(F.text.regexp(r"^\d{4}$"))
async def check_captcha(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if user_id in captcha_codes:
        if message.text == captcha_codes[user_id]:
            update_user(user_id, verifed=True)
            del captcha_codes[user_id]
            await send_welcome(message, user)
        else:
            code, img = generate_captcha()
            captcha_codes[user_id] = code

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            photo_file = FSInputFile(buf, filename="captcha.png")

            await message.answer("❌ Неверно! Попробуй ещё раз. Введи число с картинки:")
            await bot.send_photo(chat_id=message.chat.id, photo=photo_file)


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
    elif lang == "hi":
        welcome_text = (
            "👋 <b>CopRadar</b> में आपका स्वागत है!\n"
            "🗺 आपका गुमनाम अवलोकन मानचित्र।\n\n"
            "यहाँ आप कर सकते हैं:\n"
            "📍 तुरंत पुलिस पोस्ट मार्क करें\n"
            "📰 अन्य पर्यवेक्षकों से नवीनतम जानकारी प्राप्त करें\n"
            "🆘 अन्य प्रतिभागियों से मदद माँगें\n\n"
            "सभी गुमनाम 🕶️।\n\n"
            "जितना अधिक आप मदद करेंगे — आपकी रेटिंग ⭐ और रैंक बढ़ेगी:\n"
            "👶 शुरुआती\n🕵️ स्काउट\n👁️ पर्यवेक्षक\n🧐 देखने वाला\n🦅 सिस्टम की आँख"
        )

    await message.answer_photo(
        photo=photo,
        caption=welcome_text,
        reply_markup=main_menu(user['lang']),
        parse_mode="HTML"
    )


@dp.message(F.text.in_([langs["ru"], langs['en'], langs['hi']]))
async def set_lang(message: Message):
    lang_code = [k for k, v in langs.items() if v == message.text][0]
    update_user(message.from_user.id, lang=lang_code)
    user = get_user(message.from_user.id)  # Получаем актуальные данные после обновления
    await message.answer(f"✅ Язык сохранён: {message.text}", reply_markup=main_menu(user['lang']))





 
# Тексты для кнопки "Чисто"
clear_buttons = {
    "📍 Мост/Круг - Чисто": "ru",
    "📍 Bridge/Circle - Clear": "en",
    "📍 पुल/वृत्त - साफ़": "hi"
}

clear_texts = {
    "ru": "Копов нет, дорога свободна ✅",
    "en": "No cops, the road is clear ✅",
    "hi": "पुलिस नहीं है, सड़क खाली है ✅"
}

@dp.message(F.text.in_(list(clear_buttons.keys())))
async def bridge_clear(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    lang_pressed = clear_buttons[message.text]

    new_rank, new_points = update_user_activity(user_id, added_points=10)

    # Формируем читабельную строку ранга
    current_rank = f"{new_rank['ru']} / {new_rank['en']} / {new_rank['hi']} ({new_points:.0f} очков)"

    timestamp = datetime.now().strftime("%H:%M:%S")
    lat, lon = 15.64090, 73.75887

    # Отправка гео в канал
    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)

    # Сообщение в канал на всех языках
    msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{clear_texts['ru']}\n"
        f"{clear_texts['en']}\n"
        f"{clear_texts['hi']}\n"
        f"📍 Координаты: {lat}, {lon}"
    )
    await bot.send_message(chat_id=CHID, text=msg)

    # Ответ пользователю на языке кнопки
    await message.answer(
        f"✅ Отметка отправлена: {clear_texts[lang_pressed]}\n"
        f"🎖 Твой текущий ранг:\n{current_rank}",
        parse_mode="HTML"
    )

    # Обновляем рейтинг
    user = get_user(user_id)
    new_rating = min(user['rating'] + 0.2, 5)
    update_user(user_id, rating=new_rating)


cops_buttons = {
    "🚔 Мост/Круг - Копы": "ru",
    "🚔 Bridge/Circle - Cops": "en",
    "🚔 पुल/वृत्त - पुलिस": "hi"
}

cops_texts = {
    "ru": "Замечены копы 🚔",
    "en": "Cops spotted 🚔",
    "hi": "पुलिस देखी गई 🚔"
}


@dp.message(F.text.in_(list(cops_buttons.keys())))
async def bridge_cops(message: Message):
    user_id = message.from_user.id
    lang_pressed = cops_buttons[message.text]

    # Добавляем очки активности и получаем обновлённый ранг и очки
    new_rank, new_points = update_user_activity(user_id, added_points=10)

    # Формируем читабельную строку ранга
    current_rank = f"{new_rank['ru']} / {new_rank['en']} / {new_rank['hi']} ({new_points:.0f} очков)"

    timestamp = datetime.now().strftime("%H:%M:%S")
    lat, lon = 15.64090, 73.75887

    # Отправка гео в канал
    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)

    # Сообщение в канал с уже форматированным ранговым текстом
    channel_msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{cops_texts['ru']}\n"
        f"{cops_texts['en']}\n"
        f"{cops_texts['hi']}\n"
        f"📍 Координаты: {lat}, {lon}"
    )
    await bot.send_message(chat_id=CHID, text=channel_msg, parse_mode="HTML")

    # Сообщение пользователю — отметка и ранг
    await message.answer(
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
    "🚨 पुलिस रिपोर्ट करें": "hi"
}

report_texts = {
    "ru": "Замечены копы 🚔",
    "en": "Cops reported 🚔",
    "hi": "पुलिस देखी गई 🚔"
}

class ReportCops(StatesGroup):
    waiting_for_location = State()


@dp.message(F.text.in_(list(report_buttons.keys())))
async def report_cops_request(message: Message, state: FSMContext):
    lang_pressed = report_buttons[message.text]
    await state.set_state(ReportCops.waiting_for_location)  # ждем гео
    await state.update_data(lang_pressed=lang_pressed)  # сохраним язык

    if lang_pressed == "ru":
        await message.answer("📍 Отправь гео-метку места, где находятся копы. \nЧто бы отправить гео-метку, нажмите на скрепку в левом нижнем углу и выберите 'Геопозиция' ")
    elif lang_pressed == "en":
        await message.answer("📍📍 Send the location of where the cops are.\nTo send a location, tap the paperclip in the lower-left corner and select 'Location'.")
    else:
        await message.answer("📍 वह स्थान भेजें जहां पुलिस देखी गई है।\nलोकेशन भेजने के लिए, नीचे बाएँ कोने में क्लिप (📎) पर टैप करें और 'स्थान' चुनें।")

@dp.message(ReportCops.waiting_for_location, F.location)
async def report_cops_location(message: Message, state : FSMContext):
    data = await state.get_data()
    lang_pressed = data['lang_pressed']
    user_id = message.from_user.id

    new_rank, new_points = update_user_activity(user_id, added_points=10)

    # Формируем читабельную строку ранга
    current_rank = f"{new_rank['ru']} / {new_rank['en']} / {new_rank['hi']} ({new_points:.0f} очков)"

    user = get_user(message.from_user.id)
    lat, lon = message.location.latitude, message.location.longitude
    timestamp = datetime.now().strftime("%H:%M:%S")


    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)
    msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{report_texts['ru']}\n"
        f"{report_texts['en']}\n"
        f"{report_texts['hi']}\n"
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
    "✅ पुलिस नहीं": "hi"
}

nocops_texts = {
    "ru": "Копов нет, дорога свободна ✅",
    "en": "No cops, the road is clear ✅",
    "hi": "पुलिस नहीं है, सड़क खाली है ✅"
}


# FSM для ожидания гео
class NoCops(StatesGroup):
    waiting_for_location = State()


# Обработка кнопки
@dp.message(F.text.in_(list(nocops_buttons.keys())))
async def nocops_request(message: Message, state: FSMContext):
    lang_pressed = nocops_buttons[message.text]
    await state.set_state(NoCops.waiting_for_location)   # ждем гео
    await state.update_data(lang_pressed=lang_pressed)   # сохраняем язык

    prompts = {
        "ru": "📍 Отправь гео-метку места, где копов НЕТ. \nЧто бы отправить гео-метку, нажмите на скрепку в левом нижнем углу и выберите 'Геопозиция'",
        "en": "📍 Send the location where there are NO cops.\nTo send a location, tap the paperclip in the lower-left corner and select 'Location'.",
        "hi": "📍 वह स्थान भेजें जहां कोई पुलिस नहीं है।\nलोकेशन भेजने के लिए, नीचे बाएँ कोने में क्लिप (📎) पर टैप करें और 'स्थान' चुनें।"
    }
    await message.answer(prompts[lang_pressed])


# Обработка гео-метки
@dp.message(NoCops.waiting_for_location, F.location)
async def nocops_location(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_pressed = data["lang_pressed"]
    user_id = message.from_user.id

    user = get_user(message.from_user.id)
    lat, lon = message.location.latitude, message.location.longitude
    timestamp = datetime.now().strftime("%H:%M:%S")

    new_rank, new_points = update_user_activity(user_id, added_points=10)

    # Формируем читабельную строку ранга
    current_rank = f"{new_rank['ru']} / {new_rank['en']} / {new_rank['hi']} ({new_points:.0f} очков)"

    # Отправляем гео в канал
    await bot.send_location(chat_id=CHID, latitude=lat, longitude=lon)

    # Сообщение в канал на 3 языках
    msg = (
        f"⏱ {timestamp}\n"
        f"<b>{current_rank}</b>\n"
        f"{nocops_texts['ru']}\n"
        f"{nocops_texts['en']}\n"
        f"{nocops_texts['hi']}\n"
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
    "🆘 मदद चाहिए": "hi"
}

help_texts = {
    "ru": "Если нужна помощь — заходи в чат:",
    "en": "If you need help — join the chat:",
    "hi": "अगर मदद चाहिए — चैट में शामिल हों:"
}

CHAT_ID = -1002940800193


@dp.message(F.text.in_(list(help_buttons.keys())))
async def need_help(message: Message):
    lang_pressed = help_buttons[message.text]

    try:
        # Создаём временную ссылку (1 день)
        invite = await bot.create_chat_invite_link(
            chat_id=CHAT_ID,
            expire_date=int(datetime.now().timestamp()) + 86400,
            name=f"invite_for_{message.from_user.id}"
        )

        await message.answer(
            f"{help_texts[lang_pressed]}\n👉 {invite.invite_link}"
        )

    except Exception as e:
        # если бот не админ или нет прав
        await message.answer(
            f"{help_texts[lang_pressed]}\n⚠️ Ошибка: бот не может создать приглашение."
        )
        print(f"Error creating invite link: {e}")



async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

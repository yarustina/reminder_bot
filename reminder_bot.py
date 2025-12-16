from dotenv import load_dotenv
import os
import telebot
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

# ====== НАСТРОЙКИ ======
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = set(map(int, os.getenv("ALLOWED_USERS").split(",")))

if not TOKEN:
    raise RuntimeError("TOKEN не установлен в .env")

bot = telebot.TeleBot(TOKEN)

# ====== Настройка логирования ======
os.makedirs("/app/data", exist_ok=True)
logging.basicConfig(
    filename='/app/data/bot_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.debug("Бот запущен, логирование включено")

# ====== База данных ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "reminders.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        ls_text TEXT,
        sum TEXT,
        link TEXT,
        schedule_type TEXT,
        day INTEGER,
        datetime TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ====== Состояния ======
user_state = {}
temp_data = {}
confirm_state = {}

def is_allowed(uid):
    return uid in ALLOWED_USERS

# ====== Форматирование напоминания ======
def format_reminder_html(rem):
    text = f"<b>Напоминание</b>\n"
    text += f"<b>ID {rem['id']}</b>\n"
    text += f"<b>{rem['text']}</b>\n"
    if rem['ls_text']:
        text += f"ЛС: <code>{rem['ls_text']}</code>\n"
    if rem['sum']:
        text += f"Сумма: <code>{rem['sum']}</code>\n"
    if rem['link']:
        text += f'<a href="{rem["link"]}">Ссылка</a>\n'

    if rem['schedule_type'] == "monthly":
        day = rem['day'] if rem['day'] else "??"
        time_str = rem['time'] if rem['time'] else "??:??"
        text += f"⏰ Каждый месяц, день {day} в {time_str}"
    else:
        text += rem['datetime'] if rem['datetime'] else "??:??"

    return text

# ====== Меню команд ======
def send_menu(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("/add", callback_data="menu_add"),
        InlineKeyboardButton("/list", callback_data="menu_list")
    )
    markup.row(
        InlineKeyboardButton("/edit", callback_data="menu_edit"),
        InlineKeyboardButton("/del", callback_data="menu_del")
    )
    bot.send_message(chat_id, "Выбери команду:", reply_markup=markup)

# ====== /start ======
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    if not is_allowed(uid):
        return bot.reply_to(message, "Брысь.")
    bot.send_message(chat_id,
        "Привет! Я твой помощник-напоминалка.\n\n"
        "Команды:\n"
        "/add - добавить новое напоминание\n"
        "/list - показать все напоминания\n"
        "/edit <id> - редактировать напоминание\n"
        "/del <id> - удалить напоминание"
    )
    send_menu(chat_id)

# ====== /add ======
@bot.message_handler(commands=["add"])
def add_step_1(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    if not is_allowed(uid):
        return bot.reply_to(message, "Брысь.")
    user_state[uid] = {"action": "add", "step": "text"}
    temp_data[uid] = {}
    bot.send_message(chat_id, "Что нужно напомнить?")

# ====== /list ======
def list_items_from_uid(uid, chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reminders WHERE user_id=?", (uid,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        bot.send_message(chat_id, "Напоминаний нет.")
        send_menu(chat_id)
        return
    for r in rows:
        bot.send_message(
            chat_id,
            format_reminder_html(r),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    send_menu(chat_id)

# ====== /del ======
@bot.message_handler(commands=["del"])
def delete_reminder(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    if not is_allowed(uid):
        return bot.send_message(chat_id, "Брысь.")
    try:
        reminder_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        return bot.send_message(chat_id, "Нужно указать ID напоминания, например: /del 6")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reminders WHERE id=? AND user_id=?", (reminder_id, uid))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return bot.send_message(chat_id, f"Напоминание с ID {reminder_id} не найдено.")
    confirm_state[uid] = reminder_id
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Да", callback_data="del_yes"),
        InlineKeyboardButton("Нет", callback_data="del_no")
    )
    bot.send_message(chat_id, f"Удалить напоминание {reminder_id}?", reply_markup=markup)

# ====== /edit ======
@bot.message_handler(commands=["edit"])
def edit_reminder(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    if not is_allowed(uid):
        return bot.send_message(chat_id, "Брысь.")
    try:
        reminder_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        return bot.send_message(chat_id, "Нужно указать ID напоминания, например: /edit 6")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reminders WHERE id=? AND user_id=?", (reminder_id, uid))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return bot.send_message(chat_id, f"Напоминание с ID {reminder_id} не найдено.")
    temp_data[uid] = dict(row)
    user_state[uid] = {"action": "edit", "step": "text", "id": reminder_id}
    bot.send_message(chat_id, f"Редактирование напоминания {reminder_id}.\nВведите новый текст:")

# ====== Безопасные функции для temp_data и user_state ======
def get_temp(uid):
    if uid not in temp_data:
        temp_data[uid] = {}
    return temp_data[uid]

def get_state(uid):
    if uid not in user_state:
        user_state[uid] = {}
    return user_state[uid]

# ====== Callback обработка ======
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if not is_allowed(uid):
        try:
            bot.answer_callback_query(call.id, "Брысь.", show_alert=True)
        except:
            pass
        return

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    temp = get_temp(uid)
    state = get_state(uid)

    # ===== Меню =====
    if data.startswith("menu_"):
        if data == "menu_add":
            state.update({"action": "add", "step": "text"})
            temp.clear()
            bot.send_message(chat_id, "Что нужно напомнить?")
        elif data == "menu_list":
            list_items_from_uid(uid, chat_id)
        elif data == "menu_edit":
            bot.send_message(chat_id, "Редактирование через /edit <id>")
        elif data == "menu_del":
            bot.send_message(chat_id, "Удаление через /del <id>")
        return

    # ===== ЛС =====
    if data == "ls_yes":
        state["step"] = "ls_input"
        bot.send_message(chat_id, "Введи текст/цифры для ЛС:")
        return
    elif data == "ls_no":
        temp["ls_text"] = None
        state["step"] = "link_selector"
        ask_payment_link(chat_id)
        return

    # ===== Ссылка =====
    if data == "link_yes":
        state["step"] = "link_input"
        bot.send_message(chat_id, "Вставь ссылку для оплаты:")
        return
    elif data == "link_no":
        temp["link"] = None
        state["step"] = "schedule_type"
        ask_schedule_type(chat_id)
        return

    # ===== Тип напоминания =====
    if data == "one_time":
        state["step"] = "datetime"
        temp["schedule_type"] = "one_time"
        bot.send_message(chat_id, "Когда напомнить? Формат: 15.12.2025 18:00")
        return
    elif data == "monthly":
        state["step"] = "day"
        temp["schedule_type"] = "monthly"
        bot.send_message(chat_id, "Введи день месяца (1-28):")
        return

    # ===== Подтверждение удаления ======
    if data == "del_yes":
        reminder_id = confirm_state.get(uid)
        if reminder_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reminders WHERE id=? AND user_id=?", (reminder_id, uid))
            conn.commit()
            conn.close()
            bot.send_message(chat_id, f"Напоминание {reminder_id} удалено!")
            confirm_state.pop(uid, None)
            send_menu(chat_id)
        return
    elif data == "del_no":
        confirm_state.pop(uid, None)
        bot.send_message(chat_id, "Удаление отменено.")
        send_menu(chat_id)
        return

# ====== Новый шаг — спрашиваем нужна ли ссылка ======
def ask_payment_link(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Да", callback_data="link_yes"),
        InlineKeyboardButton("Нет", callback_data="link_no")
    )
    bot.send_message(chat_id, "Нужна ссылка для оплаты?", reply_markup=markup)

# ====== Ввод текста ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "text")
def text_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    temp_data[uid]["text"] = message.text.strip()
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Да", callback_data="ls_yes"),
        InlineKeyboardButton("Нет", callback_data="ls_no")
    )
    bot.send_message(chat_id, "Требуется ЛС?", reply_markup=markup)
    user_state[uid]["step"] = "ls"

# ====== Ввод ЛС ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "ls_input")
def ls_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    temp_data[uid]["ls_text"] = message.text.strip()
    user_state[uid]["step"] = "link_selector"
    ask_payment_link(chat_id)

# ====== Ввод ссылки ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "link_input")
def link_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    temp_data[uid]["link"] = text if text else None
    user_state[uid]["step"] = "schedule_type"
    ask_schedule_type(chat_id)

# ====== Выбор типа напоминания ======
def ask_schedule_type(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Разовое", callback_data="one_time"),
        InlineKeyboardButton("Регулярное", callback_data="monthly")
    )
    bot.send_message(chat_id, "Выбери тип напоминания:", reply_markup=markup)

# ====== Ввод даты и времени для one-time ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "datetime")
def datetime_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    try:
        rem_dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        if rem_dt < datetime.now():
            raise ValueError("Дата в прошлом")
    except ValueError:
        bot.send_message(chat_id, "Некорректная дата/время! Введи в формате ДД.MM.ГГГГ ЧЧ:ММ и не в прошлом.")
        return
    temp_data[uid]["datetime"] = rem_dt.strftime("%d.%m.%Y %H:%M")
    if user_state[uid]["action"] == "add":
        save_reminder(uid, temp_data[uid])
    elif user_state[uid]["action"] == "edit":
        update_reminder(uid, user_state[uid]["id"], temp_data[uid])
    bot.send_message(chat_id, "Напоминание сохранено!", disable_web_page_preview=True)
    user_state.pop(uid)
    temp_data.pop(uid)
    send_menu(chat_id)

# ====== Ввод дня для monthly ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "day")
def day_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    try:
        day = int(message.text.strip())
        if not 1 <= day <= 28:
            raise ValueError()
    except ValueError:
        bot.send_message(chat_id, "День месяца должен быть числом от 1 до 28. Попробуй ещё раз:")
        return
    temp_data[uid]["day"] = day
    user_state[uid]["step"] = "monthly_time"
    bot.send_message(chat_id, "Во сколько слать напоминание? Введи в формате ЧЧ:ММ (например, 09:30)")

# ====== Ввод времени для monthly ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "monthly_time")
def monthly_time_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    try:
        time_obj = datetime.strptime(text, "%H:%M")
    except ValueError:
        bot.send_message(chat_id, "Некорректное время! Введи в формате ЧЧ:ММ (например, 09:30)")
        return

    temp_data[uid]["time"] = time_obj.strftime("%H:%M")  # только время
    if user_state[uid]["action"] == "add":
        save_reminder(uid, temp_data[uid])
    elif user_state[uid]["action"] == "edit":
        update_reminder(uid, user_state[uid]["id"], temp_data[uid])

    bot.send_message(chat_id, "Регулярное напоминание сохранено!", disable_web_page_preview=True)
    user_state.pop(uid)
    temp_data.pop(uid)
    send_menu(chat_id)

# ====== Сохранение и обновление ======
def save_reminder(uid, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO reminders (user_id, text, ls_text, sum, link, schedule_type, day, time, datetime, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid,
        data.get("text"),
        data.get("ls_text"),
        data.get("sum"),
        data.get("link"),
        data.get("schedule_type"),
        data.get("day"),
        data.get("time"),
        data.get("datetime"),
        datetime.now().strftime("%d.%m.%Y %H:%M")
    ))
    conn.commit()
    conn.close()

    logging.debug(f"Сохранено напоминание. UID={uid}, данные: {data}")

def update_reminder(uid, reminder_id, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE reminders SET text=?, ls_text=?, sum=?, link=?, schedule_type=?, day=?, time=?, datetime=?
    WHERE id=? AND user_id=?
    """, (
        data.get("text"),
        data.get("ls_text"),
        data.get("sum"),
        data.get("link"),
        data.get("schedule_type"),
        data.get("day"),
        data.get("time") if data.get("schedule_type") == "monthly" else None,
        data.get("datetime") if data.get("schedule_type") == "one_time" else None,
        reminder_id,
        uid
    ))
    conn.commit()
    conn.close()

# ====== Проверка напоминаний ======
def check_reminders():
    now = datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reminders")
    rows = cursor.fetchall()

    for r in rows:
        try:
            # Разовое напоминание
            if r["schedule_type"] == "one_time" and r["datetime"]:
                rem_dt = datetime.strptime(r["datetime"], "%d.%m.%Y %H:%M")
                if rem_dt <= now < rem_dt + timedelta(minutes=1):
                    bot.send_message(r["user_id"], format_reminder_html(r),
                                     parse_mode="HTML",
                                     disable_web_page_preview=True)
                    cursor.execute("DELETE FROM reminders WHERE id=?", (r["id"],))

            # Регулярное напоминание
            elif r["schedule_type"] == "monthly" and r["day"]:
                if now.day == r["day"] and r["time"]:
                    rem_time = datetime.strptime(r["time"], "%H:%M").time()
                    if rem_time.hour == now.hour and rem_time.minute == now.minute:
                        bot.send_message(r["user_id"], format_reminder_html(r),
                                         parse_mode="HTML",
                                         disable_web_page_preview=True)
        except Exception as e:
            print(f"Ошибка при проверке напоминания {r['id']}: {e}")
            continue

    conn.commit()
    conn.close()

scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", minutes=1)
scheduler.start()

# ====== Ответ на посторонние сообщения ======
@bot.message_handler(func=lambda m: True)
def default_response(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    if not is_allowed(uid):
        return bot.send_message(chat_id, "Брысь.")
    bot.send_message(chat_id, "Ага. А что сделать-то надо?", disable_web_page_preview=True)
    send_menu(chat_id)

# ====== Запуск polling ======
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()

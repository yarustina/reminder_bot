from dotenv import load_dotenv
import os
import telebot
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ====== НАСТРОЙКИ ======
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = set(map(int, os.getenv("ALLOWED_USERS").split(",")))

if not TOKEN:
    raise RuntimeError("TOKEN не установлен в .env")

bot = telebot.TeleBot(TOKEN)

# ====== База данных ======
DB_FILE = "reminders.db"

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
user_state = {}      # {uid: {"action": "add/edit", "step": ..., "id": ...}}
temp_data = {}       # {uid: {...}}
confirm_state = {}   # {uid: reminder_id для удаления}

# ====== Проверка доступа ======
def is_allowed(uid):
    return uid in ALLOWED_USERS

# ====== Форматирование напоминания ======
def format_reminder_html(rem):
    text = f"<b>ID {rem['id']}</b>\n<b>{rem['text']}</b>\n"
    if rem['ls_text']:
        text += f"ЛС: <code>{rem['ls_text']}</code>\n"
    if rem['sum']:
        text += f"Сумма: <code>{rem['sum']}</code>\n"
    if rem['link']:
        text += f'<a href="{rem["link"]}">Ссылка</a>\n'
    if rem['schedule_type'] == "monthly":
        text += f"⏰ Каждый месяц, день {rem['day']} в {rem['datetime'][-5:]}"
    else:
        text += f"⏰ {rem['datetime']}"
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

# ====== Callback обработка ======
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data
    if not is_allowed(uid):
        try: bot.answer_callback_query(call.id, "Брысь.", show_alert=True)
        except: pass
        return
    try: bot.answer_callback_query(call.id)
    except: pass

    # ===== Меню =====
    if data.startswith("menu_"):
        if data == "menu_add":
            user_state[uid] = {"action": "add", "step": "text"}
            temp_data[uid] = {}
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
        user_state[uid]["step"] = "ls_input"
        bot.send_message(chat_id, "Введи текст/цифры для ЛС:")
        return
    elif data == "ls_no":
        temp_data[uid]["ls_text"] = None
        user_state[uid]["step"] = "sum"
        bot.send_message(chat_id, "Какая сумма?")
        return

    # ===== Тип напоминания =====
    if data == "one_time":
        user_state[uid]["step"] = "datetime"
        temp_data[uid]["schedule_type"] = "one_time"
        bot.send_message(chat_id, "Когда напомнить? Формат: 15.12.2025 18:00")
        return
    elif data == "monthly":
        user_state[uid]["step"] = "day"
        temp_data[uid]["schedule_type"] = "monthly"
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
    elif data == "del_no":
        confirm_state.pop(uid, None)
        bot.send_message(chat_id, "Удаление отменено.")
        send_menu(chat_id)

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
    user_state[uid]["step"] = "sum"
    bot.send_message(chat_id, "Какая сумма?")

# ====== Ввод суммы ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "sum")
def sum_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    temp_data[uid]["sum"] = message.text.strip()
    user_state[uid]["step"] = "link"
    bot.send_message(chat_id, "Вставь ссылку для оплаты:")

# ====== Ввод ссылки ======
@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "link")
def link_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    temp_data[uid]["link"] = text if text else None
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Разовое", callback_data="one_time"),
        InlineKeyboardButton("Регулярное", callback_data="monthly")
    )
    bot.send_message(chat_id, "Выбери тип напоминания:", reply_markup=markup)
    user_state[uid]["step"] = "schedule_type"

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
    temp_data[uid]["datetime"] = time_obj.strftime("01.01.2000 %H:%M")
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
    INSERT INTO reminders (user_id, text, ls_text, sum, link, schedule_type, day, datetime, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid,
        data.get("text"),
        data.get("ls_text"),
        data.get("sum"),
        data.get("link"),
        data.get("schedule_type"),
        data.get("day"),
        data.get("datetime"),
        datetime.now().strftime("%d.%m.%Y %H:%M")
    ))
    conn.commit()
    conn.close()

def update_reminder(uid, reminder_id, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE reminders SET text=?, ls_text=?, sum=?, link=?, schedule_type=?, day=?, datetime=?
    WHERE id=? AND user_id=?
    """, (
        data.get("text"),
        data.get("ls_text"),
        data.get("sum"),
        data.get("link"),
        data.get("schedule_type"),
        data.get("day"),
        data.get("datetime"),
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
            if r["schedule_type"] == "one_time" and r["datetime"]:
                rem_dt = datetime.strptime(r["datetime"], "%d.%m.%Y %H:%M")
                if rem_dt <= now < rem_dt + timedelta(minutes=1):
                    bot.send_message(
                        r["user_id"],
                        format_reminder_html(r),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    cursor.execute("DELETE FROM reminders WHERE id=?", (r["id"],))

            elif r["schedule_type"] == "monthly" and r["day"]:
                if now.day == r["day"]:
                    if r["datetime"]:
                        rem_time = datetime.strptime(r["datetime"], "%d.%m.%Y %H:%M").time()
                        if rem_time.hour == now.hour and rem_time.minute == now.minute:
                            bot.send_message(
                                r["user_id"],
                                format_reminder_html(r),
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )
                    else:
                        if now.hour == 0 and now.minute == 0:
                            bot.send_message(
                                r["user_id"],
                                format_reminder_html(r),
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )
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

# ====== Запуск ======
if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)

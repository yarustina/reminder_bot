# Reminder Bot - Telegram-бот-напоминалка

**Reminder Bot** — это персональный Telegram-бот, созданный для напоминания об оплате различных счетов и сервисов.  
Он позволяет создавать одноразовые и регулярные напоминания с указанием суммы, лицевого счёта и ссылки на оплату. Его также можно использовать для обычных бытовых напоминаний.

Как может выглядеть напоминание:

![1212 mp4_snapshot_00 00 683](https://github.com/user-attachments/assets/2ee6a2f8-ee94-4a93-9ca2-1d4f2e6563c5)




---

## 🔹 Основные возможности

- Напоминания об оплате одноразовые и ежемесячные (1-28 числа) 
- Форматирование сообщений: HTML (ссылка на сервис кликабельна, без превью)  
- Возможность добавлять:
  - ЛС (лицевой счёт в моноширном, для копирования)
  - Сумму (в моноширном, для копирования)
  - Ссылку на оплату  
- Меню с кнопками:
  - `/add` — добавить новое напоминание  
  - `/list` — показать все напоминания  
  - `/edit <id>` — редактировать напоминание  
  - `/del <id>` — удалить напоминание  
- Поддержка нескольких пользователей через `ALLOWED_USERS` (левые люди в ответ от бота будут видеть только "Брысь.")
- Бот автоматически проверяет напоминания каждую минуту  
- Работает в Docker с автоматическим перезапуском при падении

---

## 🔹 Требования

- Python 3.12+  
- Docker и Docker Compose  
- Telegram-бот (токен берётся у [BotFather](https://t.me/botfather))  
- Список разрешённых пользователей (ID можно узнать через бота [@userinfobot](https://t.me/userinfobot))
- SQLite3 (для хранения напоминаний)
- Python-библиотеки:
  - pyTelegramBotAPI  
  - APScheduler  
  - python-dotenv
---

## 🔹 Подготовка требований

- ### Python 3.12+

Проверка версии:
```bash
python3 --version
```

Установка (Ubuntu / Debian):
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

- ### Docker + Docker Compose

Проверка наличия:
```bash
docker --version
docker compose version
```

Установка Docker (Ubuntu / Debian):
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Выйдите и войдите в систему, чтобы группа применилась.

Установка Docker Compose (если отдельно):
```
sudo apt install docker-compose-plugin
```

- ### Telegram-бот

Откройте Telegram → @BotFather

Создайте бота:
```bsh
/newbot
```

Получите токен вида:
```bash
123456789:AA...xxxx
```

Сохраните токен в файле .env:
```bash
BOT_TOKEN=ваш_токен
```
- ### Список разрешённых пользователей

В проекте реализована защита: бот работает только с ID, указанных в allowed_users.

Чтобы узнать свой Telegram ID нужно написать:
```bash
@userinfobot
```
либо
```bash
@RawDataBot
```
И добавьте ID в .env:
```bash
ALLOWED_USERS=123456789,987654321
```

- ### SQLite3

База нужна для хранения данных о напоминаниях.

Проверка наличия:
```bash
sqlite3 --version
```

Установка:
```bash
sudo apt install sqlite3
```

- ### Python-библиотеки проекта

Если запускаете не через Docker, а локально, установите зависимости:
```bash
pip install pyTelegramBotAPI APScheduler python-dotenv
```

Или через requirements.txt:
```bash
pip install -r requirements.txt
```
База создаётся автоматически при первом запуске бота.

## 🔹 Настройка базы данных (SQLite)

- Бот использует SQLite для хранения напоминаний (`reminders.db`)  
- При первом запуске бот автоматически создаёт базу и таблицу `reminders`
---

## 🔹 Установка

1. Клонируйте репозиторий:

```bash
git clone https://github.com/ВАШ_ЮЗЕР_НЭЙМ/reminder-bot.git
cd reminder-bot
```
2. Настройте .env: создайте файл .env в одной директории с reminder_bot.py и в него вложите:
 ```bash
 TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER
 ALLOWED_USERS=ВАШ_tg_ID,tg_ВАШЕГО_ДРУГА,И_ТАК_ДАЛЕЕ
```
3. Соберите и запустите контейнер:
```bash
docker-compose build
```
```bash
docker-compose up -d
```
---
### Готово. Чётко.

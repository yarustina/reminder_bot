# Reminder Bot - Telegram-бот-напоминалка

**Reminder Bot** — это персональный Telegram-бот, созданный для напоминания об оплате различных счетов и сервисов.
Он позволяет создавать одноразовые и регулярные напоминания с указанием суммы, лицевого счёта и ссылки на оплату.

Его также можно использовать для обычных бытовых напоминаний.

---

### Как может выглядеть напоминание:
![IMG_1802](https://github.com/user-attachments/assets/fbc70522-e3b8-445d-821d-7f03dbca46f5)


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

## 🔹 Установите зависимости
### Python
- Проверяем обновления репозиториев:
```bash
sudo apt update
```
- Проверяем начилие python:
```bash
python3 --version
```
- Если python нет:
```bash
sudo apt install -y python3.12 python3.12-venv python3.12-distutils python3-pip
```
```bash
pip install pyTelegramBotAPI APScheduler python-dotenv
```

---

### Docker
- Проверяем наличие docker и docker compose:
```bash
docker --version
```
```bash
docker compose version
```
- Если их нет:
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
```
- Чтобы запускать docker без sudo:
```bash
sudo usermod -aG docker $USER
```

---

### SQLite
- Проверяем наличие sqlite3:
```bash
sqlite3 --version
```
- Устанавливаем sqlite3, если его нет:
```bash
sudo apt update && sudo apt install -y sqlite3
```

---

## 🔹 Настройка базы данных (SQLite)

- Бот использует SQLite для хранения напоминаний (`reminders.db`)  
- При первом запуске бот автоматически создаёт базу и таблицу `reminders`

---

## 🔹 Установка

1. Клонируйте репозиторий:

```bash
git clone https://github.com/yarustina/reminder_bot.git
```
```bash
cd reminder_bot
```
2. Настройте .env: создайте файл .env в одной директории с reminder_bot.py и в него вложите:
 ```bash
 TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER
 ALLOWED_USERS=ВАШ_tg_ID,tg_ВАШЕГО_ДРУГА,И_ТАК_ДАЛЕЕ
```
3. Соберите и запустите контейнер:
```bash
docker compose build
```
```bash
docker compose up -d
```
---
### Готово. Чётко.

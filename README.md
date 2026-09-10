# [MAIN] Teacher Schedule Bot (WIP) 

<h4 align="center">
  v0.0.3 by Lev Nalimov (@dsfpw)
</h4>

---

<h3 align="center">
  Telegram-бот для автоматического мониторинга расписания преподавателей<br>
  через API <code>teachers.it-college.ru</code>.
</h3>

<p align="center" style="margin-top: 50px;">
  <img src="./docs/images/logo_dark.png" alt="Логотип КЦТ" width="300">
</p>

<p align="center" style="margin-top: 50px;">
  <span style="color:#9504C9">©2021–2026 АНПОО «Колледж Цифровых Технологий»</span>
</p>

---

## Требования

<details>
<summary>Показать требования</summary>

<br>

* Linux (Debian 11+ / Ubuntu 22.04/24.04)
* Docker
* Docker Compose
* SSH для подключения
* Открытые порты: `80` и `443`
* Домен, направленный на IP сервера — для HTTPS webhook

</details>

## Возможности


<details>
<summary>Показать возможности</summary>

<br>

* UID используется как логин.
* Пароль вводится один раз.
* Пароль хранится только в зашифрованном виде.
* Session cookie также зашифрована.
* Автоматическое восстановление session.
* Проверка расписания каждые 10 минут *(меняется в `.env `)*.
* Автоматический diff изменений.
* Уведомления в Telegram.
* Очередь уведомлений SQLite.
* Восстановление после падения Docker/сервера.
* Startup recovery.
* Webhook Telegram.

</details>

---

## Быстрый запуск

### 1. Создать `.env`

```powershell
Copy-Item .env.example .env
```

### 2. Сгенерировать ключи

<details>
<summary>Показать команды генерации</summary>

<br>

Ключ шифрования:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Секрет webhook:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

* Первый ключ — `ENCRYPTION_KEY`
* Второй ключ — `WEBHOOK_SECRET`

Полученные значения добавить в `.env`:

```dotenv
ENCRYPTION_KEY=...
WEBHOOK_SECRET=...
```

</details>

### 3. Запустить тесты

```powershell
python run_tests.py
```

### 4. Запустить Docker

```powershell
docker compose up -d --build
```

### 5. Посмотреть статус

```powershell
docker compose ps
```

### 6. Посмотреть логи

```powershell
docker compose logs -f
```

---

## Конфигурация

Основные параметры находятся в `.env`:

<details>
<summary>Показать конфигурацию</summary>

<br>

```dotenv
BOT_TOKEN=
WEBHOOK_BASE_URL=
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=
ENCRYPTION_KEY=

PORT=8080
POLL_INTERVAL=600
REQUEST_TIMEOUT=20
NOTIFICATION_RETRY_INTERVAL=30
```

`POLL_INTERVAL=600` — проверка расписания каждые 10 минут.

</details>

---

## Дополнительные материалы

* [DOCKER](./docs/DOCKER.md) — про Docker Image (WIP)
* [SERVER_SETUP](./docs/SERVER_SETUP.md) — про готовую серверную установку (WIP)
* [TODO...](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

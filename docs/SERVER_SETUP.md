# [SERVER_SETUP] Teacher Schedule Bot (WIP)

<h4 align="center">
  v0.0.4 by Lev Nalimov (@dsfpw)
</h4>


---

<h3 align="center">SERVER_SETUP СЕКЦИЯ</h3>

<p align="center" style="margin-top: 50px;">
  <img src="./images/logo_dark.png" alt="Логотип КЦТ" width="300">
</p>

<p align="center" style="margin-top: 50px;">
  <span style="color:#9504C9">©2021–2026 АНПОО «Колледж Цифровых Технологий»</span>
</p>

---

## Установка на сервер

<p>
  Готовые версии бота публикуются в разделе
  <b>GitHub Releases</b>.
  Для установки на сервер не требуется собирать Docker Image вручную.
</p>

<p>
  Необходимо скачать <code>.tar</code> нужной версии из Release и загрузить его на сервер.
</p>

---

### 1. Скачать релиз

Откройте:

<p>
  <a href="https://github.com/DangettoSir/teacher-bot-cdt/releases">
    GitHub Releases
  </a>
</p>

<p>
  Выберите необходимую версию, например <code>v0.0.1</code>,
  и скачайте файл:
</p>

```text
teacher-bot-cdt-v0.0.1.tar
```

---

### 2. Подготовить директорию на сервере

Подключитесь к серверу по SSH и создайте директорию:

```bash
mkdir -p /opt/teacher-bot
cd /opt/teacher-bot
```

---

### 3. Загрузить Docker Image

С локального компьютера загрузите скачанный `.tar`:

```powershell
scp .\teacher-bot-cdt-v0.0.1.tar root@SERVER_IP:/opt/teacher-bot/
```

Замените:

```text
SERVER_IP
```

на IP-адрес вашего сервера.

После загрузки подключитесь к серверу:

```bash
ssh root@SERVER_IP
```

Перейдите в директорию:

```bash
cd /opt/teacher-bot
```

---

### 4. Загрузить Image в Docker

```bash
docker load -i teacher-bot-cdt-v0.0.1.tar
```

Проверьте наличие образа:

```bash
docker images
```

Должен появиться:

```text
teacher-bot-cdt
```

---

## Настройка

### 5. Создать `.env`

Создайте файл:

```bash
nano .env
```

Заполните его:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

WEBHOOK_BASE_URL=https://ВАШ_ДОМЕН
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=YOUR_WEBHOOK_SECRET

ENCRYPTION_KEY=YOUR_ENCRYPTION_KEY

DATABASE_PATH=/app/data/bot.db

CHECK_INTERVAL=600
```

<p>
  <b>Важно:</b> файл <code>.env</code> содержит секретные данные и
  не должен публиковаться в GitHub.
</p>

---

### 6. Сгенерировать ключ шифрования

Для генерации ключа:

```bash
docker run --rm python:3.13-alpine \
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Полученное значение поместите в:

```env
ENCRYPTION_KEY=...
```

<p>
  <code>ENCRYPTION_KEY</code> используется для шифрования паролей и
  сессионных данных преподавателей в базе данных.
</p>

---

## 7. Использовать готовый docker-compose.yml

<p> В корне репозитория уже находится готовый файл <code>docker-compose.server.yml</code>. Создавать его вручную не требуется. </p>

<p> Скопируйте файл <code>docker-compose.server.yml</code> в директорию <code>/opt/teacher-bot/</code> на сервере. </p>

<p> Перед запуском убедитесь, что версия Docker Image в файле соответствует загруженной версии релиза. </p>

Например:

image: teacher-bot-cdt:0.0.1

<p> Если используется релиз <code>v0.0.2</code>, укажите: </p>

image: teacher-bot-cdt:0.0.2

<p> Остальные параметры <code>docker-compose.yml</code> менять не требуется. </p>

---

## Первый запуск

### 8. Запустить контейнер

```bash
mkdir -p data
docker compose -f docker-compose.server.yml up -d
```

Проверить состояние:

```bash
docker compose -f docker-compose.server.yml ps
```

Ожидается:

```text
NAME               STATUS
teacher-bot-cdt    Up
```

---

### 9. Проверить логи

```bash
docker compose -f docker-compose.server.yml logs -f
```

Для выхода из просмотра логов:

```text
Ctrl + C
```

<p>
  Контейнер при этом продолжит работать.
</p>

---

## Настройка HTTPS и Webhook

<p>
  Telegram Webhook должен работать через HTTPS.
  Если на сервере используется Nginx и Certbot,
  запросы необходимо проксировать на порт <code>8080</code>.
</p>

Пример конфигурации Nginx:

```nginx
server {
    server_name ВАШ_ДОМЕН;

    location / {
        proxy_pass http://127.0.0.1:8080;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl;
}
```

<p>
  После изменения конфигурации:
</p>

```bash
nginx -t
systemctl reload nginx
```

<p>
  В <code>.env</code> должен быть указан тот же домен:
</p>

```env
WEBHOOK_BASE_URL=https://ВАШ_ДОМЕН
WEBHOOK_PATH=/telegram/webhook
```

<p>
  Сам бот автоматически регистрирует Webhook в Telegram при запуске.
</p>

---

## Проверка работоспособности

### Проверить контейнер

```bash
docker compose ps
```

### Проверить Healthcheck

```bash
curl http://127.0.0.1:8080/health
```

Ожидается успешный HTTP-ответ.

### Проверить логи

```bash
docker compose logs --tail=100
```

---

## Автозапуск

Docker должен автоматически запускаться после перезагрузки сервера:

```bash
systemctl enable --now docker
```

Проверка:

```bash
systemctl is-enabled docker
systemctl is-active docker
```

Ожидаемый результат:

```text
enabled
active
```

<p>
  Контейнер использует:
</p>

```yaml
restart: unless-stopped
```

<p>
  Поэтому после перезагрузки сервера Docker автоматически восстановит контейнер.
</p>

---

## Обновление на новую версию

При выходе новой версии:

### 1. Скачать новый `.tar`

Например:

```text
teacher-bot-cdt-v0.0.2.tar
```

из GitHub Releases.

### 2. Загрузить на сервер

```powershell
scp .\teacher-bot-cdt-v0.0.2.tar root@SERVER_IP:/opt/teacher-bot/
```

### 3. Загрузить Image

```bash
docker load -i teacher-bot-cdt-v0.0.2.tar
```

### 4. Изменить версию в `docker-compose.yml`

```yaml
image: teacher-bot-cdt:0.0.2
```

### 5. Перезапустить

```bash
docker compose up -d
```

### 6. Проверить

```bash
docker compose ps
docker compose logs --tail=100
```

<p>
  База данных находится в <code>./data</code>, поэтому обновление Docker Image
  не удаляет сохранённые настройки, учётные данные и состояние мониторинга.
</p>

---

## Траблшутинг


---

<details>
<summary><b>Контейнер не запускается</b></summary>

Проверить:

```bash
docker compose ps
```

Логи:

```bash
docker compose logs --tail=200
```

Проверить `.env`:

```bash
cat .env
```

<p>
  Не публикуйте содержимое <code>.env</code> в GitHub или других открытых местах.
</p>

</details>

---

<details>
<summary><b>Webhook не работает</b></summary>

Проверить Nginx:

```bash
nginx -t
systemctl status nginx
```

Проверить контейнер:

```bash
docker compose -f docker-compose.server.yml ps
```

Проверить локальный endpoint:

```bash
curl http://127.0.0.1:8080/health
```

Проверить HTTPS:

```bash
curl https://ВАШ_ДОМЕН/health
```

</details>

---

## Структура директории на сервере

После установки:

```text
/opt/teacher-bot/
│
├── .env
├── docker-compose.server.yml
├── teacher-bot-cdt-v0.0.1.tar
│
└── data/
    └── bot.db
```

<p>
  <code>.env</code> и <code>data/</code> не должны попадать в Git.
</p>

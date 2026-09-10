# [DOCKER] Teacher Schedule Bot (WIP)

<h4 align="center">
  v0.0.4 by Lev Nalimov (@dsfpw)
</h4>


---

<h3 align="center">DOCKER СЕКЦИЯ</h3>

<p align="center" style="margin-top: 50px;">
  <img src="./images/logo_dark.png" alt="Логотип КЦТ" width="300">
</p>

<p align="center" style="margin-top: 50px;">
  <span style="color:#9504C9">©2021–2026 АНПОО «Колледж Цифровых Технологий»</span>
</p>

---

## Docker Image

<p>
  Сборка Docker-образа выполняется локально, после чего готовый образ переносится на сервер.
</p>

<details>
<summary><b>1. Сборка образа</b></summary>

```bash
docker build -t teacher-bot-cdt .
```

</details>

<details>
<summary><b>2. Экспорт образа</b></summary>

```bash
docker save teacher-bot-cdt -o teacher-bot-cdt.tar
```

</details>

<details>
<summary><b>3. Загрузка образа на сервер</b></summary>

<p>Из PowerShell на локальном компьютере:</p>

```powershell
scp .\teacher-bot.tar user@SERVER_IP:/opt/teacher-bot/
```

</details>

<details>
<summary><b>4. Загрузка образа в Docker на сервере</b></summary>

```bash
docker load -i teacher-bot-cdt.tar
```

</details>

---

## Траблшутинг

<p>
  Раздел с типовыми проблемами при установке и настройке Docker.
</p>

<details>
<summary><b>Нет Docker</b></summary>

<p>Если Docker не установлен, установите его:</p>

```bash
apt update
apt install -y docker.io
```

<p>После установки проверьте версии:</p>

```bash
docker --version
docker compose version
```

<p>При успешной установке будет отображаться примерно:</p>

```text
Docker version x.x.x, build fffffff
Docker Compose version vX.x.x
```

</details>

---

<details>
<summary><b>E: Unable to locate package docker-compose-plugin</b></summary>

<p>
  В стандартном репозитории Ubuntu может отсутствовать пакет
  <code>docker-compose-plugin</code>. В таком случае используется официальный репозиторий Docker.
</p>

<h4>1. Устанавливаем необходимые пакеты</h4>

```bash
apt update
apt install -y ca-certificates curl
```

<h4>2. Добавляем ключ Docker</h4>

```bash
install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

chmod a+r /etc/apt/keyrings/docker.asc
```

<h4>3. Добавляем официальный репозиторий Docker</h4>

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
```

<h4>4. Устанавливаем Docker Engine и Compose</h4>

```bash
apt update

apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

<h4>5. Проверяем установку</h4>

```bash
docker --version
docker compose version
```

<p>При успешной установке:</p>

```text
Docker version x.x.x, build fffffff
Docker Compose version vX.x.x
```

</details>

---

## Автозапуск Docker

<p>
  Чтобы Docker автоматически запускался после перезагрузки сервера:
</p>

```bash
systemctl enable --now docker
```

<p>Проверка:</p>

```bash
systemctl is-enabled docker
systemctl is-active docker
```

<p>Ожидаемый результат:</p>

```text
enabled
active
```

---

## Автоперезапуск контейнера

<p>
  В <code>docker-compose.yml</code> рекомендуется использовать:
</p>

```yaml
services:
  bot:
    restart: unless-stopped
```

<p>
  Это обеспечивает автоматический запуск контейнера после перезагрузки сервера,
  перезапуска Docker или падения приложения.
</p>

---

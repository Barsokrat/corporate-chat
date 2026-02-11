# Corporate Chat Backend

Мультиплатформенный корпоративный чат на FastAPI с поддержкой WebSocket для real-time сообщений.

## Возможности

- ✅ Регистрация и авторизация пользователей (JWT)
- ✅ Личные сообщения 1-на-1
- ✅ Групповые чаты с неограниченным количеством участников
- ✅ Real-time доставка сообщений через WebSocket
- ✅ Загрузка и скачивание файлов
- ✅ История сообщений
- ✅ Индикатор "печатает..."
- ✅ REST API для всех платформ (Web, iOS, Android, Desktop)

## Технологии

- **Backend**: Python 3.11 + FastAPI
- **WebSocket**: встроенный в FastAPI
- **Database**: PostgreSQL
- **Cache**: Redis
- **Storage**: S3-совместимое хранилище
- **Deploy**: Docker + Docker Compose

## Быстрый старт (локально)

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и настройте переменные:

```bash
cp .env.example .env
```

### 3. Запуск (без Docker)

```bash
python main.py
```

Сервер запустится на `http://localhost:8000`

API документация: `http://localhost:8000/docs`

## Запуск с Docker

### 1. Запустить все сервисы

```bash
docker-compose up -d
```

Это запустит:
- FastAPI приложение (порт 8000)
- PostgreSQL (порт 5432)
- Redis (порт 6379)
- Nginx (порт 80)

### 2. Проверить логи

```bash
docker-compose logs -f app
```

### 3. Остановить

```bash
docker-compose down
```

### 4. Инициализация тестовых данных

После запуска можно создать тестовых пользователей и группы:

```bash
python3 seed_data.py
```

Это создаст:
- 3 пользователя (2 обычных + 1 админ)
- 2 группы (общий чат и рабочая группа)
- Несколько тестовых сообщений

**Тестовые аккаунты:**

| Username | Password | Роль | Полное имя |
|----------|----------|------|------------|
| testuser1 | passworD1 | user | Test User 1 |
| testuser2 | passworD1 | user | Test User 2 |
| testadmin2 | password | admin | Test Admin 2 |

## API Endpoints

### Аутентификация

- `POST /register` - Регистрация пользователя
- `POST /token` - Вход (получение JWT токена)
- `GET /users/me` - Информация о текущем пользователе

### Пользователи

- `GET /users` - Список всех пользователей

### Сообщения

- `POST /messages` - Отправить сообщение (личное или в группу)
- `GET /messages?recipient_id={id}` - История личных сообщений
- `GET /messages?group_id={id}` - История группового чата

### Группы

- `POST /groups` - Создать группу
- `GET /groups` - Список групп пользователя
- `GET /groups/{id}` - Информация о группе
- `POST /groups/{id}/members` - Добавить участников в группу

### Файлы

- `POST /upload` - Загрузить файл

### WebSocket

- `WS /ws/{user_id}` - WebSocket подключение для real-time сообщений

## Пример использования WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/user-id-here');

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log('Новое сообщение:', message);
};

// Отправить индикатор "печатает"
ws.send(JSON.stringify({
    type: 'typing',
    recipient_id: 'recipient-user-id'
}));

// Пинг для проверки соединения
ws.send(JSON.stringify({ type: 'ping' }));
```

## Деплой на AWS

### 1. Подключение к серверу

```bash
ssh -i ../_keys_ssh_api/AWS_Key_pair_1.pem ubuntu@your-server-ip
```

### 2. Установка Docker на сервере

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

### 3. Загрузка кода на сервер

```bash
# На локальной машине
rsync -avz -e "ssh -i ../_keys_ssh_api/AWS_Key_pair_1.pem" \
  --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
  . ubuntu@your-server-ip:~/corporate-chat-backend/
```

### 4. Запуск на сервере

```bash
# На сервере
cd ~/corporate-chat-backend
cp .env.example .env
# Отредактировать .env с реальными значениями
nano .env

# Запустить
docker-compose up -d
```

### 5. Проверка

```bash
curl http://your-server-ip:8000/
```

## Структура проекта

```
corporate-chat-backend/
├── main.py                 # Основное приложение FastAPI
├── requirements.txt        # Python зависимости
├── Dockerfile             # Docker образ
├── docker-compose.yml     # Оркестрация сервисов
├── nginx.conf             # Конфигурация Nginx
├── .env.example           # Пример переменных окружения
└── README.md              # Документация
```

## Roadmap

- [ ] Миграция с in-memory хранилища на PostgreSQL
- [ ] Интеграция Redis для pub/sub между несколькими инстансами
- [ ] S3 загрузка файлов
- [ ] Поддержка голосовых сообщений
- [ ] Импорт чатов из Telegram (опционально)
- [ ] Push уведомления для мобильных приложений
- [ ] E2E шифрование
- [ ] Поиск по сообщениям

## Лицензия

MIT

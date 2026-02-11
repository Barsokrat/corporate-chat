#!/bin/bash

# Скрипт для удалённого деплоя на EC2 через SSH
# Использование: ./remote_deploy.sh

INSTANCE_IP="18.191.43.123"
KEY_PATH="/Users/victorboro/Projects/wwl/_keys_ssh_api/AWS_Key_pair_1.pem"
USER="ec2-user"

echo "=== Удалённый деплой Corporate Chat на AWS ==="
echo "Инстанс: $USER@$INSTANCE_IP"
echo ""

# Проверка доступности
echo "Проверка доступности инстанса..."
if ! ping -c 1 -W 2 $INSTANCE_IP >/dev/null 2>&1; then
    echo "ОШИБКА: Инстанс недоступен. Проверьте что он запущен."
    exit 1
fi

# Копируем скрипт на сервер и запускаем
echo "Подключение к серверу..."
ssh -o ConnectTimeout=30 \
    -o ServerAliveInterval=10 \
    -o StrictHostKeyChecking=no \
    -i "$KEY_PATH" \
    "$USER@$INSTANCE_IP" \
    'bash -s' << 'ENDSSH'

set -e

echo "=== Установка зависимостей ==="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "Установка Docker..."
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER

    # Перезапуск сессии для применения группы docker
    exec sg docker -c "$0 $*"
fi

# Проверка Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Установка Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker-compose --version)"

# Клонирование репозитория
REPO_DIR="$HOME/corporate-chat"

if [ -d "$REPO_DIR" ]; then
    echo "Обновление репозитория..."
    cd $REPO_DIR
    git pull
else
    echo "Клонирование репозитория..."
    git clone https://github.com/Barsokrat/corporate-chat.git $REPO_DIR
    cd $REPO_DIR
fi

# Создание .env
echo "Создание .env файла..."
cat > .env << 'EOF'
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=postgresql://chatuser:chatpassword@db:5432/corporate_chat
REDIS_URL=redis://redis:6379/0
EOF

# Создание директории uploads
mkdir -p uploads

# Остановка старых контейнеров
echo "Остановка старых контейнеров..."
docker-compose down 2>/dev/null || true

# Запуск
echo "Запуск контейнеров..."
docker-compose up -d --build

echo ""
echo "Ожидание запуска сервисов..."
sleep 10

# Создание тестовых данных
echo "Создание тестовых пользователей..."
docker-compose exec -T app python seed_data.py || echo "Пропускаем seed_data (возможно уже есть)"

echo ""
echo "=== Деплой завершён! ==="
echo ""
echo "Чат доступен: http://18.191.43.123"
echo ""
echo "Тестовые пользователи:"
echo "  testuser1 / passworD1"
echo "  testuser2 / passworD1"
echo "  testadmin2 / password (admin)"
echo ""
echo "Команды для управления:"
echo "  Логи: docker-compose logs -f"
echo "  Остановка: docker-compose down"
echo "  Перезапуск: docker-compose restart"

ENDSSH

echo ""
echo "=== Готово! ==="

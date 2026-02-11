#!/bin/bash

# Скрипт для деплоя Corporate Chat на AWS

set -e

echo "=== Деплой Corporate Chat на AWS ==="
echo ""

# Установка Docker (если не установлен)
if ! command -v docker &> /dev/null; then
    echo "Установка Docker..."
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
fi

# Установка Docker Compose (если не установлен)
if ! command -v docker-compose &> /dev/null; then
    echo "Установка Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Установка Git (если не установлен)
if ! command -v git &> /dev/null; then
    echo "Установка Git..."
    sudo yum install -y git
fi

echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker-compose --version)"
echo ""

# Клонирование репозитория
REPO_DIR="/home/ec2-user/corporate-chat"

if [ -d "$REPO_DIR" ]; then
    echo "Обновление репозитория..."
    cd $REPO_DIR
    git pull
else
    echo "Клонирование репозитория..."
    git clone https://github.com/Barsokrat/corporate-chat.git $REPO_DIR
    cd $REPO_DIR
fi

# Создание .env файла
echo "Создание .env файла..."
cat > .env << 'EOF'
SECRET_KEY=your-secret-key-change-this-in-production-$(openssl rand -hex 32)
DATABASE_URL=postgresql://chatuser:chatpassword@db:5432/corporate_chat
REDIS_URL=redis://redis:6379/0
EOF

# Создание директории для uploads
mkdir -p uploads

# Остановка старых контейнеров (если есть)
echo "Остановка старых контейнеров..."
docker-compose down || true

# Сборка и запуск
echo "Запуск контейнеров..."
docker-compose up -d --build

echo ""
echo "=== Деплой завершен! ==="
echo ""
echo "Чат доступен по адресу: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
echo "Для просмотра логов: docker-compose logs -f"
echo "Для остановки: docker-compose down"
echo ""
echo "Создание тестовых данных..."
docker-compose exec -T app python seed_data.py

echo ""
echo "Готово! Тестовые пользователи:"
echo "  testuser1 / passworD1"
echo "  testuser2 / passworD1"
echo "  testadmin2 / password (admin)"

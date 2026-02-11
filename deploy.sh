#!/bin/bash

# Скрипт деплоя на AWS сервер

set -e

# Конфигурация
SSH_KEY="../_keys_ssh_api/AWS_Key_pair_1.pem"
SERVER_USER="ubuntu"
SERVER_IP=""  # Заполнить IP сервера
REMOTE_DIR="~/corporate-chat-backend"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка переменных
if [ -z "$SERVER_IP" ]; then
    echo -e "${RED}Ошибка: SERVER_IP не установлен${NC}"
    echo "Отредактируйте deploy.sh и укажите IP сервера"
    exit 1
fi

if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Ошибка: SSH ключ не найден: $SSH_KEY${NC}"
    exit 1
fi

echo -e "${GREEN}=== Деплой Corporate Chat Backend ===${NC}\n"

# 1. Синхронизация файлов
echo -e "${YELLOW}1. Синхронизация файлов на сервер...${NC}"
rsync -avz --progress \
    -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'venv' \
    --exclude 'uploads' \
    --exclude '.DS_Store' \
    . ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/

echo -e "${GREEN}✓ Файлы синхронизированы${NC}\n"

# 2. Подключение к серверу и запуск
echo -e "${YELLOW}2. Подключение к серверу и запуск...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    set -e

    cd ~/corporate-chat-backend

    # Проверка .env файла
    if [ ! -f .env ]; then
        echo "⚠️  .env файл не найден, копирую из .env.example"
        cp .env.example .env
        echo "⚠️  ВАЖНО: Отредактируйте .env файл с реальными значениями!"
    fi

    # Остановка старых контейнеров
    echo "Остановка старых контейнеров..."
    docker-compose down || true

    # Сборка и запуск
    echo "Сборка и запуск контейнеров..."
    docker-compose build
    docker-compose up -d

    # Проверка статуса
    echo ""
    echo "Статус контейнеров:"
    docker-compose ps

    echo ""
    echo "Последние логи:"
    docker-compose logs --tail=20 app

ENDSSH

echo -e "\n${GREEN}=== Деплой завершён ===${NC}"
echo -e "API доступен по адресу: ${GREEN}http://${SERVER_IP}:8000${NC}"
echo -e "Документация API: ${GREEN}http://${SERVER_IP}:8000/docs${NC}"
echo ""
echo -e "Для просмотра логов выполните:"
echo -e "${YELLOW}ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_IP} 'cd ${REMOTE_DIR} && docker-compose logs -f app'${NC}"

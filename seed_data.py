#!/usr/bin/env python3
"""
Скрипт для инициализации тестовых данных в чате

Создаёт:
- 3 тестовых пользователя (2 обычных + 1 админ)
- 2 группы (одна со всеми пользователями, другая с двумя)
- Несколько тестовых сообщений

Запуск:
    python seed_data.py
"""

import requests
import json

API_URL = "http://localhost:8000"

# Тестовые пользователи
USERS = [
    {
        "username": "testuser1",
        "full_name": "Test User 1",
        "email": "test1@test.com",
        "password": "passworD1",
        "role": "user"
    },
    {
        "username": "testuser2",
        "full_name": "Test User 2",
        "email": "test2@test.com",
        "password": "passworD1",
        "role": "user"
    },
    {
        "username": "testadmin2",
        "full_name": "Test Admin 2",
        "email": "testadmin1@test.com",
        "password": "password",
        "role": "admin"
    }
]

def register_users():
    """Регистрация тестовых пользователей"""
    print("🔧 Регистрация пользователей...\n")

    tokens = {}
    user_ids = {}

    for user in USERS:
        try:
            response = requests.post(
                f"{API_URL}/register",
                json=user
            )

            if response.status_code == 200:
                data = response.json()
                tokens[user["username"]] = data["access_token"]

                # Получить ID пользователя
                me_response = requests.get(
                    f"{API_URL}/users/me",
                    headers={"Authorization": f"Bearer {data['access_token']}"}
                )
                user_info = me_response.json()
                user_ids[user["username"]] = user_info["id"]

                role_emoji = "👑" if user["role"] == "admin" else "👤"
                print(f"   {role_emoji} {user['full_name']} (@{user['username']}) - OK")
            else:
                error = response.json()
                if "already exists" in error.get("detail", ""):
                    print(f"   ⚠️  {user['username']} уже существует")
                else:
                    print(f"   ❌ {user['username']}: {error.get('detail', 'Ошибка')}")
        except Exception as e:
            print(f"   ❌ {user['username']}: {e}")

    print()
    return tokens, user_ids

def create_groups(tokens, user_ids):
    """Создание групп"""
    print("👥 Создание групп...\n")

    # Взять токен первого пользователя для создания групп
    token = list(tokens.values())[0]
    all_user_ids = list(user_ids.values())

    groups = []

    # Группа 1: Все пользователи
    try:
        group1 = {
            "name": "Общий чат",
            "description": "Группа для всех пользователей",
            "member_ids": all_user_ids[1:]  # Все кроме создателя (он добавится автоматически)
        }

        response = requests.post(
            f"{API_URL}/groups",
            headers={"Authorization": f"Bearer {token}"},
            json=group1
        )

        if response.status_code == 200:
            group_data = response.json()
            groups.append(group_data)
            print(f"   ✅ Группа '{group1['name']}' создана ({len(group_data['members'])} участников)")
        else:
            print(f"   ❌ Ошибка создания группы: {response.json()}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # Группа 2: Только два пользователя
    try:
        group2 = {
            "name": "Рабочая группа",
            "description": "Группа для двух пользователей",
            "member_ids": [all_user_ids[1]]  # Только второй пользователь
        }

        response = requests.post(
            f"{API_URL}/groups",
            headers={"Authorization": f"Bearer {token}"},
            json=group2
        )

        if response.status_code == 200:
            group_data = response.json()
            groups.append(group_data)
            print(f"   ✅ Группа '{group2['name']}' создана ({len(group_data['members'])} участников)")
        else:
            print(f"   ❌ Ошибка создания группы: {response.json()}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    print()
    return groups

def send_test_messages(tokens, user_ids, groups):
    """Отправка тестовых сообщений"""
    print("💬 Отправка тестовых сообщений...\n")

    # Личное сообщение от testuser1 к testuser2
    try:
        token1 = tokens.get("testuser1")
        user2_id = user_ids.get("testuser2")

        if token1 and user2_id:
            message = {
                "content": "Привет! Это тестовое личное сообщение.",
                "recipient_id": user2_id
            }

            response = requests.post(
                f"{API_URL}/messages",
                headers={"Authorization": f"Bearer {token1}"},
                json=message
            )

            if response.status_code == 200:
                print("   ✅ Личное сообщение отправлено (testuser1 → testuser2)")
    except Exception as e:
        print(f"   ❌ Ошибка отправки личного сообщения: {e}")

    # Сообщение в группу "Общий чат"
    try:
        token1 = tokens.get("testuser1")

        if token1 and len(groups) > 0:
            message = {
                "content": "Всем привет! Добро пожаловать в общий чат! 👋",
                "group_id": groups[0]["id"]
            }

            response = requests.post(
                f"{API_URL}/messages",
                headers={"Authorization": f"Bearer {token1}"},
                json=message
            )

            if response.status_code == 200:
                print(f"   ✅ Сообщение в группу '{groups[0]['name']}' отправлено")
    except Exception as e:
        print(f"   ❌ Ошибка отправки в группу: {e}")

    # Сообщение в "Рабочую группу"
    try:
        token2 = tokens.get("testuser2")

        if token2 and len(groups) > 1:
            message = {
                "content": "Начинаем работу над проектом!",
                "group_id": groups[1]["id"]
            }

            response = requests.post(
                f"{API_URL}/messages",
                headers={"Authorization": f"Bearer {token2}"},
                json=message
            )

            if response.status_code == 200:
                print(f"   ✅ Сообщение в группу '{groups[1]['name']}' отправлено")
    except Exception as e:
        print(f"   ❌ Ошибка отправки в рабочую группу: {e}")

    print()

def main():
    print("=" * 60)
    print("🚀 Инициализация тестовых данных для Corporate Chat")
    print("=" * 60)
    print()

    # Проверка доступности сервера
    try:
        response = requests.get(f"{API_URL}/api")
        if response.status_code != 200:
            print("❌ Сервер недоступен. Убедитесь что запущен: docker-compose up")
            return
    except Exception as e:
        print(f"❌ Не удалось подключиться к серверу: {e}")
        print("   Убедитесь что запущен: docker-compose up")
        return

    # Регистрация пользователей
    tokens, user_ids = register_users()

    if not tokens:
        print("❌ Не удалось зарегистрировать пользователей")
        return

    # Создание групп
    groups = create_groups(tokens, user_ids)

    # Отправка тестовых сообщений
    send_test_messages(tokens, user_ids, groups)

    # Вывод информации
    print("=" * 60)
    print("✅ Инициализация завершена!")
    print("=" * 60)
    print()
    print("📋 Тестовые аккаунты:")
    print()
    for user in USERS:
        role = "Админ" if user["role"] == "admin" else "Пользователь"
        print(f"   {user['full_name']}")
        print(f"   Username: {user['username']}")
        print(f"   Password: {user['password']}")
        print(f"   Роль: {role}")
        print()

    print("🌐 Веб-интерфейс: http://localhost:8000")
    print("📚 API документация: http://localhost:8000/docs")
    print("⚙️  Админ-панель: http://localhost:8000/static/admin.html")
    print()

if __name__ == "__main__":
    main()

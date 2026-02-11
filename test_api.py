#!/usr/bin/env python3
"""
Тестовый скрипт для проверки корпоративного чата
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_api():
    print("🧪 Тестирование Corporate Chat API\n")

    # 1. Проверка статуса сервера
    print("1️⃣  Проверка статуса сервера...")
    response = requests.get(f"{BASE_URL}/")
    print(f"   ✅ Статус: {response.json()['status']}")
    print(f"   📝 Версия: {response.json()['version']}\n")

    # 2. Регистрация первого пользователя
    print("2️⃣  Регистрация пользователя Ivan...")
    user1 = {
        "username": "ivan_test",
        "email": "ivan.test@company.com",
        "password": "password123",
        "full_name": "Иван Тестов"
    }
    response = requests.post(f"{BASE_URL}/register", json=user1)
    token1 = response.json()["access_token"]
    print(f"   ✅ Зарегистрирован: {user1['full_name']}")
    print(f"   🔑 Токен: {token1[:50]}...\n")

    # 3. Регистрация второго пользователя
    print("3️⃣  Регистрация пользователя Maria...")
    user2 = {
        "username": "maria_test",
        "email": "maria.test@company.com",
        "password": "password123",
        "full_name": "Мария Тестова"
    }
    response = requests.post(f"{BASE_URL}/register", json=user2)
    token2 = response.json()["access_token"]
    print(f"   ✅ Зарегистрирована: {user2['full_name']}\n")

    # 4. Получение информации о текущем пользователе
    print("4️⃣  Получение информации о пользователе Ivan...")
    headers1 = {"Authorization": f"Bearer {token1}"}
    response = requests.get(f"{BASE_URL}/users/me", headers=headers1)
    user_info = response.json()
    print(f"   ✅ ID: {user_info['id']}")
    print(f"   ✅ Username: {user_info['username']}")
    print(f"   ✅ Email: {user_info['email']}\n")

    # 5. Получение списка пользователей
    print("5️⃣  Получение списка всех пользователей...")
    response = requests.get(f"{BASE_URL}/users", headers=headers1)
    users = response.json()
    print(f"   ✅ Найдено пользователей: {len(users)}")
    for u in users[-2:]:  # Показать последних двух
        print(f"      • {u['full_name']} (@{u['username']})")
    print()

    # 6. Отправка личного сообщения
    print("6️⃣  Отправка личного сообщения от Ivan к Maria...")
    maria_id = next(u['id'] for u in users if u['username'] == 'maria_test')
    message_data = {
        "content": "Привет, Мария! Как дела?",
        "recipient_id": maria_id
    }
    response = requests.post(f"{BASE_URL}/messages", json=message_data, headers=headers1)
    print(f"   Response status: {response.status_code}")
    print(f"   Response text: {response.text}")
    message = response.json()
    print(f"   ✅ Сообщение отправлено")
    print(f"   📨 ID: {message['id']}")
    print(f"   💬 Содержание: {message['content']}\n")

    # 7. Создание группы
    print("7️⃣  Создание группы 'Team Chat'...")
    ivan_id = user_info['id']
    group_data = {
        "name": "Team Chat",
        "description": "Командный чат для обсуждения проектов",
        "member_ids": [maria_id]
    }
    headers1 = {"Authorization": f"Bearer {token1}"}
    response = requests.post(f"{BASE_URL}/groups", json=group_data, headers=headers1)
    group = response.json()
    print(f"   ✅ Группа создана")
    print(f"   🆔 ID: {group['id']}")
    print(f"   👥 Участников: {len(group['members'])}\n")

    # 8. Отправка сообщения в группу
    print("8️⃣  Отправка сообщения в группу...")
    message_data = {
        "content": "Всем привет! Начинаем обсуждение проекта.",
        "group_id": group['id']
    }
    response = requests.post(f"{BASE_URL}/messages", json=message_data, headers=headers1)
    group_message = response.json()
    print(f"   ✅ Сообщение отправлено в группу")
    print(f"   💬 Содержание: {group_message['content']}\n")

    # 9. Получение списка групп для Maria
    print("9️⃣  Получение списка групп для Maria...")
    headers2 = {"Authorization": f"Bearer {token2}"}
    response = requests.get(f"{BASE_URL}/groups", headers=headers2)
    groups = response.json()
    print(f"   ✅ Maria участвует в {len(groups)} группах")
    for g in groups:
        print(f"      • {g['name']}: {g['description']}\n")

    # 10. Получение истории сообщений
    print("🔟 Получение истории личных сообщений между Ivan и Maria...")
    response = requests.get(f"{BASE_URL}/messages?recipient_id={maria_id}", headers=headers1)
    messages = response.json()
    print(f"   ✅ Найдено сообщений: {len(messages)}")
    for msg in messages:
        print(f"      📨 {msg['sender_name']}: {msg['content']}")
    print()

    # 11. Получение истории группового чата
    print("1️⃣1️⃣  Получение истории группового чата...")
    response = requests.get(f"{BASE_URL}/messages?group_id={group['id']}", headers=headers2)
    group_messages = response.json()
    print(f"   ✅ Сообщений в группе: {len(group_messages)}")
    for msg in group_messages:
        print(f"      💬 {msg['sender_name']}: {msg['content']}")
    print()

    print("=" * 60)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)
    print(f"\n📚 Документация API: {BASE_URL}/docs")
    print(f"🔌 WebSocket endpoint: ws://localhost:8000/ws/{{user_id}}\n")

if __name__ == "__main__":
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка: Не удалось подключиться к серверу")
        print("   Убедитесь что сервер запущен: docker-compose up")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

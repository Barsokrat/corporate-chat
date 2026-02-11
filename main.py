from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import jwt
import bcrypt
import asyncio
import json
import uuid
import os

app = FastAPI(title="Corporate Chat API", version="1.0.0")

# Подключение статических файлов
if os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")

# CORS для мультиплатформенности
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация (позже вынести в .env)
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Временное хранилище (позже заменить на PostgreSQL)
users_db: Dict[str, dict] = {}
messages_db: List[dict] = []
groups_db: Dict[str, dict] = {}

# WebSocket менеджер для real-time сообщений
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_groups: Dict[str, List[str]] = {}  # user_id -> [group_ids]

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"User {user_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"User {user_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                print(f"[WebSocket] Sending to {user_id}: file_url={message.get('file_url')}, file_name={message.get('file_name')}, file_size={message.get('file_size')}")
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                print(f"Error sending to {user_id}: {e}")
                self.disconnect(user_id)

    async def broadcast_to_group(self, message: dict, group_id: str):
        """Отправить сообщение всем участникам группы"""
        if group_id in groups_db:
            members = groups_db[group_id].get("members", [])
            for member_id in members:
                await self.send_personal_message(message, member_id)

    async def broadcast_to_all(self, message: dict):
        """Отправить всем подключенным пользователям"""
        disconnected = []
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to {user_id}: {e}")
                disconnected.append(user_id)

        for user_id in disconnected:
            self.disconnect(user_id)

manager = ConnectionManager()

# Pydantic модели
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    role: Optional[str] = "user"  # "user" или "admin"

class UserLogin(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class MessageCreate(BaseModel):
    content: Optional[str] = ""  # Текст сообщения (может быть пустым если есть файл)
    recipient_id: Optional[str] = None  # Для личных сообщений
    group_id: Optional[str] = None  # Для групповых сообщений
    file_url: Optional[str] = None  # URL загруженного файла
    file_name: Optional[str] = None  # Имя файла
    file_size: Optional[int] = None  # Размер файла

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    member_ids: List[str] = []

class MessageResponse(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    content: str
    recipient_id: Optional[str] = None
    group_id: Optional[str] = None
    timestamp: datetime
    type: str  # "personal" or "group"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None

class GroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    members: List[str]
    created_at: datetime
    created_by: str

# Утилиты для JWT
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    username = verify_token(token)
    if username is None or username not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return users_db[username]

async def get_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    return current_user

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# API Endpoints

@app.get("/")
async def root():
    # Если есть веб-интерфейс, показать его
    if os.path.exists("web/index.html"):
        return FileResponse("web/index.html")

    return {
        "message": "Corporate Chat API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "websocket": "/ws/{user_id}",
            "register": "/register",
            "login": "/token",
            "web": "/static/index.html"
        }
    }

@app.get("/api")
async def api_info():
    return {
        "message": "Corporate Chat API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "websocket": "/ws/{user_id}",
            "register": "/register",
            "login": "/token"
        }
    }

@app.post("/register", response_model=Token)
async def register(user: UserCreate):
    if user.username in users_db:
        raise HTTPException(status_code=400, detail="Username already exists")

    user_id = str(uuid.uuid4())

    # Первый зарегистрированный пользователь становится админом
    role = "admin" if len(users_db) == 0 else (user.role if user.role in ["user", "admin"] else "user")

    users_db[user.username] = {
        "id": user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "password_hash": hash_password(user.password),
        "created_at": datetime.utcnow().isoformat()
    }

    access_token = create_access_token(data={"sub": user.username, "user_id": user_id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user["username"], "user_id": user["id"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "role": current_user.get("role", "user")
    }

@app.get("/users", response_model=List[dict])
async def get_users(current_user: dict = Depends(get_current_user)):
    """Получить список всех пользователей"""
    return [
        {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"]
        }
        for user in users_db.values()
    ]

@app.post("/messages", response_model=MessageResponse)
async def send_message(message: MessageCreate, current_user: dict = Depends(get_current_user)):
    if not message.recipient_id and not message.group_id:
        raise HTTPException(status_code=400, detail="Must specify recipient_id or group_id")

    msg_id = str(uuid.uuid4())
    msg_type = "group" if message.group_id else "personal"

    message_data = {
        "id": msg_id,
        "sender_id": current_user["id"],
        "sender_name": current_user["full_name"],
        "content": message.content,
        "recipient_id": message.recipient_id,
        "group_id": message.group_id,
        "timestamp": datetime.utcnow().isoformat(),
        "type": msg_type,
        "file_url": message.file_url,
        "file_name": message.file_name,
        "file_size": message.file_size
    }

    messages_db.append(message_data)

    # Отправить через WebSocket
    if message.group_id:
        await manager.broadcast_to_group(message_data, message.group_id)
    elif message.recipient_id:
        await manager.send_personal_message(message_data, message.recipient_id)
        # Отправить копию отправителю для синхронизации
        await manager.send_personal_message(message_data, current_user["id"])

    message_data_copy = message_data.copy()
    message_data_copy["timestamp"] = datetime.fromisoformat(message_data["timestamp"])
    return MessageResponse(**message_data_copy)

@app.get("/messages", response_model=List[MessageResponse])
async def get_messages(
    recipient_id: Optional[str] = None,
    group_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Получить историю сообщений"""
    filtered_messages = []

    for msg in messages_db:
        if group_id and msg.get("group_id") == group_id:
            filtered_messages.append(msg)
        elif recipient_id:
            # Личные сообщения между current_user и recipient_id
            if (msg.get("sender_id") == current_user["id"] and msg.get("recipient_id") == recipient_id) or \
               (msg.get("sender_id") == recipient_id and msg.get("recipient_id") == current_user["id"]):
                filtered_messages.append(msg)
        elif not group_id and not recipient_id:
            # Все сообщения пользователя
            if msg.get("sender_id") == current_user["id"] or msg.get("recipient_id") == current_user["id"]:
                filtered_messages.append(msg)

    # Сортировать по времени от старых к новым
    filtered_messages.sort(key=lambda x: x.get("timestamp", ""))

    # Взять последние limit сообщений
    filtered_messages = filtered_messages[-limit:]

    result = []
    for msg in filtered_messages:
        msg_copy = msg.copy()
        msg_copy["timestamp"] = datetime.fromisoformat(msg["timestamp"])
        result.append(MessageResponse(**msg_copy))
    return result

@app.post("/groups", response_model=GroupResponse)
async def create_group(group: GroupCreate, current_user: dict = Depends(get_current_user)):
    group_id = str(uuid.uuid4())

    # Добавить создателя в участники
    members = list(set([current_user["id"]] + group.member_ids))

    group_data = {
        "id": group_id,
        "name": group.name,
        "description": group.description,
        "members": members,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": current_user["id"]
    }

    groups_db[group_id] = group_data

    group_data_copy = group_data.copy()
    group_data_copy["created_at"] = datetime.fromisoformat(group_data["created_at"])
    return GroupResponse(**group_data_copy)

@app.get("/groups", response_model=List[GroupResponse])
async def get_groups(current_user: dict = Depends(get_current_user)):
    """Получить список групп пользователя"""
    user_groups = [
        group for group in groups_db.values()
        if current_user["id"] in group["members"]
    ]

    result = []
    for group in user_groups:
        group_copy = group.copy()
        group_copy["created_at"] = datetime.fromisoformat(group["created_at"])
        result.append(GroupResponse(**group_copy))
    return result

@app.get("/groups/{group_id}", response_model=GroupResponse)
async def get_group(group_id: str, current_user: dict = Depends(get_current_user)):
    if group_id not in groups_db:
        raise HTTPException(status_code=404, detail="Group not found")

    group = groups_db[group_id]

    if current_user["id"] not in group["members"]:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    group_copy = group.copy()
    group_copy["created_at"] = datetime.fromisoformat(group["created_at"])
    return GroupResponse(**group_copy)

@app.post("/groups/{group_id}/members")
async def add_group_members(
    group_id: str,
    member_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    if group_id not in groups_db:
        raise HTTPException(status_code=404, detail="Group not found")

    group = groups_db[group_id]

    if current_user["id"] not in group["members"]:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    # Добавить новых участников
    group["members"] = list(set(group["members"] + member_ids))

    return {"message": "Members added successfully", "members": group["members"]}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Загрузка файла"""
    # Создать директорию для загрузок
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
    saved_filename = f"{file_id}.{file_extension}"
    file_path = os.path.join(upload_dir, saved_filename)

    # Сохранить файл
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    file_size = len(contents)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "saved_filename": saved_filename,
        "content_type": file.content_type,
        "size": file_size,
        "url": f"/files/{saved_filename}",
        "uploaded_by": current_user["id"],
        "uploaded_at": datetime.utcnow().isoformat()
    }

@app.get("/files/{filename}")
async def download_file(filename: str):
    """Скачать файл"""
    file_path = os.path.join("uploads", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Получать данные от клиента (пинги, команды)
            data = await websocket.receive_text()

            # Обработка входящих команд через WebSocket
            try:
                message_data = json.loads(data)

                if message_data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message_data.get("type") == "typing":
                    # Уведомить о том, что пользователь печатает
                    typing_notification = {
                        "type": "typing",
                        "user_id": user_id,
                        "recipient_id": message_data.get("recipient_id"),
                        "group_id": message_data.get("group_id")
                    }

                    if message_data.get("group_id"):
                        await manager.broadcast_to_group(typing_notification, message_data["group_id"])
                    elif message_data.get("recipient_id"):
                        await manager.send_personal_message(typing_notification, message_data["recipient_id"])

            except json.JSONDecodeError:
                pass  # Игнорировать невалидный JSON

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        print(f"User {user_id} disconnected")

# === АДМИНСКИЕ ЭНДПОИНТЫ ===

@app.get("/admin/users")
async def admin_get_all_users(admin: dict = Depends(get_admin_user)):
    """Получить список всех пользователей с полной информацией (только для админов)"""
    return [
        {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user.get("role", "user"),
            "created_at": user.get("created_at")
        }
        for user in users_db.values()
    ]

@app.put("/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    user_update: UserUpdate,
    admin: dict = Depends(get_admin_user)
):
    """Обновить данные пользователя (только для админов)"""
    # Найти пользователя
    target_user = None
    for user in users_db.values():
        if user["id"] == user_id:
            target_user = user
            break

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновить данные
    if user_update.full_name:
        target_user["full_name"] = user_update.full_name
    if user_update.email:
        target_user["email"] = user_update.email
    if user_update.role and user_update.role in ["user", "admin"]:
        target_user["role"] = user_update.role

    return {
        "message": "User updated successfully",
        "user": {
            "id": target_user["id"],
            "username": target_user["username"],
            "email": target_user["email"],
            "full_name": target_user["full_name"],
            "role": target_user.get("role", "user")
        }
    }

@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Удалить пользователя (только для админов)"""
    # Нельзя удалить самого себя
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    # Найти и удалить пользователя
    username_to_delete = None
    for username, user in users_db.items():
        if user["id"] == user_id:
            username_to_delete = username
            break

    if not username_to_delete:
        raise HTTPException(status_code=404, detail="User not found")

    del users_db[username_to_delete]

    return {"message": "User deleted successfully"}

@app.get("/admin/stats")
async def admin_get_stats(admin: dict = Depends(get_admin_user)):
    """Получить статистику системы (только для админов)"""
    total_messages = len(messages_db)

    return {
        "total_users": len(users_db),
        "total_groups": len(groups_db),
        "total_messages": total_messages,
        "active_connections": len(manager.active_connections),
        "admins_count": len([u for u in users_db.values() if u.get("role") == "admin"]),
        "users_count": len([u for u in users_db.values() if u.get("role") == "user"])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

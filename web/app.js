// Конфигурация API - автоматическое определение
const API_URL = window.location.protocol + '//' + window.location.host;
const WS_URL = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host;

// Глобальное состояние
let currentUser = null;
let token = null;
let ws = null;
let activeChat = null;
let users = [];
let groups = [];
let messages = {};
let typingTimeout = null;
let unreadMessages = {}; // { chatId: count }

// Звук уведомления
const notificationSound = new Audio('/static/notification.mp3');
notificationSound.volume = 0.5; // Устанавливаем громкость
notificationSound.preload = 'auto'; // Предзагружаем звук

// === ИНИЦИАЛИЗАЦИЯ ===
document.addEventListener('DOMContentLoaded', () => {
    // Проверка сохраненного токена
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');

    if (savedToken && savedUser) {
        token = savedToken;
        currentUser = JSON.parse(savedUser);
        showChatScreen();
    }

    initAuthListeners();
    // initChatListeners() теперь вызывается в showChatScreen()

    // Разблокировка звука при первом взаимодействии (для мобильных)
    const unlockAudio = () => {
        notificationSound.play().then(() => {
            notificationSound.pause();
            notificationSound.currentTime = 0;
            console.log('[Audio] Звук разблокирован для воспроизведения');
        }).catch(err => {
            console.log('[Audio] Ожидание взаимодействия для разблокировки звука');
        });
        // Удаляем обработчик после первого срабатывания
        document.removeEventListener('click', unlockAudio);
        document.removeEventListener('touchstart', unlockAudio);
    };
    document.addEventListener('click', unlockAudio, { once: true });
    document.addEventListener('touchstart', unlockAudio, { once: true });

    // Переподключение WebSocket при возврате в приложение (для iOS Safari)
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && currentUser && ws) {
            // Приложение стало видимым
            console.log('[WebSocket] Проверка соединения после возврата');
            if (ws.readyState !== WebSocket.OPEN) {
                console.log('[WebSocket] Переподключение...');
                connectWebSocket();
            }
            // Обновляем список сообщений активного чата
            if (activeChat) {
                loadMessages();
            }
        }
    });

    // Обработка виртуального viewport для мобильных (Android)
    if (window.visualViewport && window.innerWidth <= 768) {
        window.visualViewport.addEventListener('resize', () => {
            const messageInputContainer = document.querySelector('.message-input-container');
            if (messageInputContainer) {
                // Двигаем поле ввода вверх когда появляется клавиатура
                const offsetTop = window.visualViewport.offsetTop;
                const viewportHeight = window.visualViewport.height;
                const windowHeight = window.innerHeight;

                if (viewportHeight < windowHeight) {
                    // Клавиатура открыта
                    messageInputContainer.style.bottom = `${windowHeight - viewportHeight - offsetTop}px`;
                } else {
                    // Клавиатура закрыта
                    messageInputContainer.style.bottom = '0px';
                }
            }
        });
    }
});

// === АВТОРИЗАЦИЯ ===
function initAuthListeners() {
    // Переключение табов
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`${tab}-form`).classList.add('active');
        });
    });

    // Вход
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;

        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch(`${API_URL}/token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData
            });

            if (!response.ok) throw new Error('Неверный username или пароль');

            const data = await response.json();
            token = data.access_token;
            localStorage.setItem('token', token);

            await loadCurrentUser();
            showChatScreen();
        } catch (error) {
            showError('login-error', error.message);
        }
    });

    // Регистрация
    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fullname = document.getElementById('register-fullname').value;
        const username = document.getElementById('register-username').value;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;

        try {
            const response = await fetch(`${API_URL}/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    full_name: fullname,
                    username: username,
                    email: email,
                    password: password
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка регистрации');
            }

            const data = await response.json();
            token = data.access_token;
            localStorage.setItem('token', token);

            await loadCurrentUser();
            showChatScreen();
        } catch (error) {
            showError('register-error', error.message);
        }
    });
}

async function loadCurrentUser() {
    const response = await fetch(`${API_URL}/users/me`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    currentUser = await response.json();
    localStorage.setItem('user', JSON.stringify(currentUser));
}

function showError(elementId, message) {
    const errorEl = document.getElementById(elementId);
    errorEl.textContent = message;
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), 5000);
}

function showChatScreen() {
    document.getElementById('auth-screen').classList.remove('active');
    document.getElementById('chat-screen').classList.add('active');
    document.getElementById('current-user-name').textContent = currentUser.full_name;

    // Показать кнопку админки если пользователь - админ
    if (currentUser.role === 'admin') {
        showAdminButton();
    }

    // Инициализировать обработчики чата (теперь когда DOM готов)
    initChatListeners();

    connectWebSocket();
    loadUsers();
    loadGroups();
}

function showAdminButton() {
    const sidebarHeader = document.querySelector('.sidebar-header');
    const adminBtn = document.createElement('button');
    adminBtn.className = 'btn btn-icon';
    adminBtn.title = 'Админ-панель';
    adminBtn.textContent = '⚙️';
    adminBtn.onclick = () => window.location.href = '/static/admin.html';
    sidebarHeader.appendChild(adminBtn);
}

// === WEBSOCKET ===
function connectWebSocket() {
    ws = new WebSocket(`${WS_URL}/ws/${currentUser.id}`);

    ws.onopen = () => {
        console.log('WebSocket подключен');
        // Отправляем пинг каждые 30 секунд
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket ошибка:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket отключен, переподключение...');
        setTimeout(connectWebSocket, 3000);
    };
}

// === НЕПРОЧИТАННЫЕ СООБЩЕНИЯ ===
function getUnreadCount(chatId, type) {
    return unreadMessages[chatId] || 0;
}

function incrementUnreadCount(chatId) {
    unreadMessages[chatId] = (unreadMessages[chatId] || 0) + 1;
    console.log(`[Unread] Increment: chatId=${chatId}, count=${unreadMessages[chatId]}`);
    updateContactBadge(chatId);
    playNotificationSound();
}

function playNotificationSound() {
    // Для мобильных используем вибрацию как альтернативу
    if ('vibrate' in navigator) {
        // Паттерн вибрации: [вибрация, пауза, вибрация]
        navigator.vibrate([200, 100, 200]);
        console.log('[Notification] Вибрация включена');
    }

    // Пробуем также воспроизвести звук (на десктопе сработает)
    notificationSound.currentTime = 0; // Сбрасываем на начало
    const playPromise = notificationSound.play();

    if (playPromise !== undefined) {
        playPromise.then(() => {
            console.log('[Audio] Звук воспроизведён успешно');
        }).catch(error => {
            console.log('[Audio] Звук заблокирован, используем только вибрацию:', error.message);
        });
    }
}

function clearUnreadCount(chatId) {
    unreadMessages[chatId] = 0;
    console.log(`[Unread] Clear: chatId=${chatId}`);
    updateContactBadge(chatId);
}

function updateContactBadge(chatId) {
    const contactItem = document.querySelector(`.contact-item[data-id="${chatId}"]`);
    console.log(`[Unread] Update badge: chatId=${chatId}, found=${!!contactItem}`);

    if (!contactItem) {
        console.warn(`[Unread] Contact item not found for chatId=${chatId}`);
        return;
    }

    const existingBadge = contactItem.querySelector('.unread-badge');
    const count = unreadMessages[chatId] || 0;

    console.log(`[Unread] Existing badge=${!!existingBadge}, count=${count}`);

    if (count > 0) {
        if (existingBadge) {
            existingBadge.textContent = count;
            console.log(`[Unread] Updated existing badge to ${count}`);
        } else {
            const badge = document.createElement('span');
            badge.className = 'unread-badge';
            badge.textContent = count;
            badge.style.backgroundColor = '#e74c3c'; // Явно задаём цвет для отладки
            contactItem.appendChild(badge);
            console.log(`[Unread] Created new badge with count ${count}`);
        }
    } else if (existingBadge) {
        existingBadge.remove();
        console.log(`[Unread] Removed badge`);
    }
}

function handleWebSocketMessage(data) {
    if (data.type === 'pong') {
        return;
    }

    if (data.type === 'typing') {
        // Показать индикатор "печатает"
        if (activeChat &&
            (data.recipient_id === currentUser.id || data.group_id === activeChat.id)) {
            showTypingIndicator(data.user_id);
        }
        return;
    }

    // Новое сообщение
    if (data.id && (data.content || data.file_url)) {
        addMessageToCache(data);

        const isActiveChat = activeChat &&
            ((data.recipient_id === currentUser.id && data.sender_id === activeChat.id) ||
             (data.sender_id === currentUser.id && data.recipient_id === activeChat.id) ||
             (data.group_id === activeChat.id));

        // Проверяем действительно ли чат виден (не только открыт в памяти)
        const chatMainVisible = document.querySelector('.chat-main')?.style.display !== 'none' &&
                                document.querySelector('.chat-active')?.style.display !== 'none';

        const shouldShowInChat = isActiveChat && chatMainVisible;

        // Если это активный и ВИДИМЫЙ чат - добавить сообщение
        if (shouldShowInChat) {
            // Проверить, не добавлено ли уже это сообщение
            const container = document.getElementById('messages-container');
            const existingMessage = container.querySelector(`[data-message-id="${data.id}"]`);
            if (!existingMessage) {
                appendMessage(data);
            }
        } else if (data.sender_id !== currentUser.id) {
            // Если сообщение не в видимом чате и не от нас - увеличить счётчик непрочитанных
            const chatId = data.group_id || data.sender_id;
            incrementUnreadCount(chatId);
        }

        // Обновить список контактов
        updateContactLastMessage(data);
    }
}

function showTypingIndicator(userId) {
    const indicator = document.getElementById('typing-indicator');
    const user = users.find(u => u.id === userId);
    if (user) {
        indicator.querySelector('.typing-name').textContent = user.full_name;
        indicator.style.display = 'block';

        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
            indicator.style.display = 'none';
        }, 3000);
    }
}

// === ЧАТ ===
function initChatListeners() {
    // Кнопка "Назад" для мобильных
    document.getElementById('mobile-back-btn').addEventListener('click', () => {
        const sidebar = document.querySelector('.sidebar');
        const chatMain = document.querySelector('.chat-main');
        sidebar.classList.remove('hide');
        chatMain.classList.remove('show');
    });

    // Переключение табов sidebar
    document.querySelectorAll('.sidebar-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const type = btn.dataset.type;
            document.querySelectorAll('.sidebar-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            if (type === 'users') {
                renderContactsList(users.filter(u => u.id !== currentUser.id), 'user');
            } else {
                renderContactsList(groups, 'group');
            }
        });
    });

    // Отправка сообщения
    document.getElementById('message-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await sendMessage();
    });

    // Индикатор "печатает"
    let typingTimer;
    document.getElementById('message-input').addEventListener('input', () => {
        clearTimeout(typingTimer);

        if (ws && ws.readyState === WebSocket.OPEN && activeChat) {
            const typingData = {
                type: 'typing',
                user_id: currentUser.id
            };

            if (activeChat.type === 'user') {
                typingData.recipient_id = activeChat.id;
            } else {
                typingData.group_id = activeChat.id;
            }

            ws.send(JSON.stringify(typingData));
        }
    });

    // Создание группы
    document.getElementById('create-group-btn').addEventListener('click', () => {
        showCreateGroupModal();
    });

    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
        });
    });

    document.getElementById('create-group-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await createGroup();
    });

    // Прикрепление файла
    document.getElementById('attach-btn').addEventListener('click', () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '*/*';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (file) {
                await uploadAndSendFile(file);
            }
        };
        input.click();
    });

    // Выход
    document.getElementById('logout-btn').addEventListener('click', logout);
}

async function loadUsers() {
    try {
        const response = await fetch(`${API_URL}/users`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        users = await response.json();

        // Показать пользователей по умолчанию
        const activeTab = document.querySelector('.sidebar-tab.active').dataset.type;
        if (activeTab === 'users') {
            renderContactsList(users.filter(u => u.id !== currentUser.id), 'user');
        }
    } catch (error) {
        console.error('Ошибка загрузки пользователей:', error);
    }
}

async function loadGroups() {
    try {
        const response = await fetch(`${API_URL}/groups`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        groups = await response.json();

        const activeTab = document.querySelector('.sidebar-tab.active').dataset.type;
        if (activeTab === 'groups') {
            renderContactsList(groups, 'group');
        }
    } catch (error) {
        console.error('Ошибка загрузки групп:', error);
    }
}

function renderContactsList(contacts, type) {
    const container = document.getElementById('contacts-list');
    container.innerHTML = '';

    if (contacts.length === 0) {
        container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-secondary);">Нет контактов</div>';
        return;
    }

    contacts.forEach(contact => {
        const item = document.createElement('div');
        item.className = 'contact-item';
        item.dataset.id = contact.id;
        item.dataset.type = type;

        const emoji = type === 'group' ? '💼' : '👤';
        const name = type === 'group' ? contact.name : contact.full_name;
        const status = type === 'group' ? `${contact.members.length} участников` : 'Online';

        // Подсчёт непрочитанных сообщений
        const unreadCount = getUnreadCount(contact.id, type);
        const unreadBadge = unreadCount > 0 ? `<span class="unread-badge">${unreadCount}</span>` : '';

        item.innerHTML = `
            <div class="contact-avatar">${emoji}</div>
            <div class="contact-info">
                <div class="contact-name">${name}</div>
                <div class="contact-last-message">${status}</div>
            </div>
            ${unreadBadge}
        `;

        // Поддержка touch и click событий для мобильных устройств
        const handleOpen = () => {
            openChat(contact, type);
        };

        item.addEventListener('click', handleOpen);
        item.addEventListener('touchend', (e) => {
            e.preventDefault();
            handleOpen();
        });

        container.appendChild(item);
    });
}

async function openChat(contact, type) {
    activeChat = { ...contact, type };

    // Обнулить счётчик непрочитанных
    clearUnreadCount(contact.id);

    // Обновить UI
    document.querySelectorAll('.contact-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`.contact-item[data-id="${contact.id}"]`)?.classList.add('active');

    document.querySelector('.chat-welcome').style.display = 'none';
    document.querySelector('.chat-active').style.display = 'flex';

    // Для мобильных: скрыть sidebar и показать chat-main
    const sidebar = document.querySelector('.sidebar');
    const chatMain = document.querySelector('.chat-main');
    if (window.innerWidth <= 768) {
        sidebar.classList.add('hide');
        chatMain.classList.add('show');
    }

    const emoji = type === 'group' ? '💼' : '👤';
    const name = type === 'group' ? contact.name : contact.full_name;
    const status = type === 'group' ? `${contact.members.length} участников` : 'Online';

    document.querySelector('.chat-avatar').textContent = emoji;
    document.getElementById('active-chat-name').textContent = name;
    document.getElementById('active-chat-status').textContent = status;

    // Загрузить историю сообщений
    await loadMessages();
}

async function loadMessages() {
    try {
        let url = `${API_URL}/messages?`;
        if (activeChat.type === 'user') {
            url += `recipient_id=${activeChat.id}`;
        } else {
            url += `group_id=${activeChat.id}`;
        }

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const msgs = await response.json();

        // Сохранить в кеш
        msgs.forEach(msg => addMessageToCache(msg));

        // Отобразить
        renderMessages(msgs);
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
    }
}

function renderMessages(msgs) {
    const container = document.getElementById('messages-container');
    container.innerHTML = '';

    // Отсортировать сообщения по времени (от старых к новым)
    const sortedMsgs = msgs.sort((a, b) => {
        return new Date(a.timestamp) - new Date(b.timestamp);
    });

    sortedMsgs.forEach(msg => {
        appendMessage(msg, false);
    });

    scrollToBottom();
}

function appendMessage(msg, scroll = true) {
    console.log('appendMessage called with:', msg);

    const container = document.getElementById('messages-container');

    const isSent = msg.sender_id === currentUser.id;
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
    messageDiv.setAttribute('data-message-id', msg.id);

    const time = new Date(msg.timestamp).toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });

    let contentHTML = '';

    // Если есть файл - показать его
    if (msg.file_url) {
        const fileSize = msg.file_size ? formatFileSize(msg.file_size) : '';
        contentHTML += `
            <div class="message-bubble">
                <a href="${API_URL}${msg.file_url}" target="_blank" download="${msg.file_name}" class="message-file-link">
                    📎 ${escapeHtml(msg.file_name)} ${fileSize ? `(${fileSize})` : ''}
                </a>
            </div>
        `;
    }

    // Текстовое сообщение
    if (msg.content) {
        contentHTML += `<div class="message-bubble">${escapeHtml(msg.content)}</div>`;
    }

    messageDiv.innerHTML = `
        <div class="message-avatar">${isSent ? '👤' : '👤'}</div>
        <div class="message-content">
            ${!isSent && activeChat.type === 'group' ? `<div class="message-sender">${msg.sender_name}</div>` : ''}
            ${contentHTML}
            <div class="message-time">${time}</div>
        </div>
    `;

    container.appendChild(messageDiv);

    if (scroll) {
        scrollToBottom();
    }
}

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    container.scrollTop = container.scrollHeight;
}

async function sendMessage() {
    const input = document.getElementById('message-input');
    const content = input.value.trim();

    if (!content || !activeChat) return;

    try {
        const messageData = {
            content: content
        };

        if (activeChat.type === 'user') {
            messageData.recipient_id = activeChat.id;
        } else {
            messageData.group_id = activeChat.id;
        }

        const response = await fetch(`${API_URL}/messages`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(messageData)
        });

        if (!response.ok) throw new Error('Ошибка отправки сообщения');

        const msg = await response.json();

        // Сообщение добавится через WebSocket
        input.value = '';
    } catch (error) {
        console.error('Ошибка отправки:', error);
        alert('Не удалось отправить сообщение');
    }
}

function showCreateGroupModal() {
    const modal = document.getElementById('create-group-modal');
    const membersList = document.getElementById('group-members-list');

    membersList.innerHTML = '';
    users.filter(u => u.id !== currentUser.id).forEach(user => {
        const item = document.createElement('label');
        item.className = 'member-item';
        item.innerHTML = `
            <input type="checkbox" value="${user.id}">
            <div class="member-avatar">👤</div>
            <div class="member-name">${user.full_name}</div>
        `;
        membersList.appendChild(item);
    });

    modal.classList.add('active');
}

async function createGroup() {
    const name = document.getElementById('group-name').value;
    const description = document.getElementById('group-description').value;
    const checkboxes = document.querySelectorAll('#group-members-list input:checked');
    const memberIds = Array.from(checkboxes).map(cb => cb.value);

    if (memberIds.length === 0) {
        alert('Выберите хотя бы одного участника');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/groups`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                member_ids: memberIds
            })
        });

        if (!response.ok) throw new Error('Ошибка создания группы');

        document.getElementById('create-group-modal').classList.remove('active');
        document.getElementById('create-group-form').reset();

        await loadGroups();

        // Переключиться на таб групп
        document.querySelector('.sidebar-tab[data-type="groups"]').click();
    } catch (error) {
        console.error('Ошибка создания группы:', error);
        alert('Не удалось создать группу');
    }
}

function addMessageToCache(msg) {
    const chatId = msg.group_id || (msg.sender_id === currentUser.id ? msg.recipient_id : msg.sender_id);
    if (!messages[chatId]) {
        messages[chatId] = [];
    }

    // Проверить, есть ли уже это сообщение
    if (!messages[chatId].find(m => m.id === msg.id)) {
        messages[chatId].push(msg);
    }
}

function updateContactLastMessage(msg) {
    // TODO: Обновить последнее сообщение в списке контактов
}

async function uploadAndSendFile(file) {
    console.log('uploadAndSendFile called with file:', file);

    if (!activeChat) {
        alert('Выберите чат для отправки файла');
        return;
    }

    console.log('Active chat:', activeChat);

    // Проверка размера (макс 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        alert('Файл слишком большой. Максимальный размер: 10MB');
        return;
    }

    console.log('File size OK:', file.size);

    try {
        // Показать индикатор загрузки
        const input = document.getElementById('message-input');
        const originalPlaceholder = input.placeholder;
        input.placeholder = `Загрузка ${file.name}...`;
        input.disabled = true;

        console.log('Starting file upload...');

        // Загрузить файл на сервер
        const formData = new FormData();
        formData.append('file', file);

        const uploadResponse = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        console.log('Upload response status:', uploadResponse.status);

        if (!uploadResponse.ok) {
            const errorText = await uploadResponse.text();
            console.error('Upload failed:', errorText);
            throw new Error('Ошибка загрузки файла');
        }

        const fileData = await uploadResponse.json();
        console.log('File uploaded:', fileData);

        // Отправить сообщение с файлом
        const messageData = {
            content: '', // Можно добавить комментарий к файлу
            file_url: fileData.url,
            file_name: fileData.filename,
            file_size: fileData.size
        };

        if (activeChat.type === 'user') {
            messageData.recipient_id = activeChat.id;
        } else {
            messageData.group_id = activeChat.id;
        }

        console.log('Sending message with file:', messageData);

        const response = await fetch(`${API_URL}/messages`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(messageData)
        });

        console.log('Message response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Message send failed:', errorText);
            throw new Error('Ошибка отправки сообщения');
        }

        const sentMessage = await response.json();
        console.log('Message sent successfully:', sentMessage);

        // Сообщение придёт через WebSocket, не добавляем его вручную

        // Сбросить состояние
        input.placeholder = originalPlaceholder;
        input.disabled = false;
        input.focus();

    } catch (error) {
        console.error('Ошибка отправки файла:', error);
        alert('Не удалось отправить файл');

        document.getElementById('message-input').placeholder = 'Введите сообщение...';
        document.getElementById('message-input').disabled = false;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');

    if (ws) {
        ws.close();
    }

    location.reload();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

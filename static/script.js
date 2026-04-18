/**
 * 美术需求澄清助手 - 前端交互脚本
 * 功能：常驻可编辑卡片、保存修改、导出JSON文件、复制卡片
 */

// 全局状态
const state = {
    sessionId: null,
    isLoading: false,
    card: null          // 当前卡片数据
};

// DOM元素
const elements = {
    messages: document.getElementById('messages'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    newChatBtn: document.getElementById('newChatBtn'),
    cardPanel: document.getElementById('cardPanel'),
    cardContent: document.getElementById('cardContent'),
    progressIndicator: document.getElementById('progressIndicator'),
    copyCardBtn: document.getElementById('copyCardBtn'),
    saveCardBtn: document.getElementById('saveCardBtn'),
    exportJsonBtn: document.getElementById('exportJsonBtn')
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    autoResizeTextarea();
    loadInitialCard();  // 加载当前会话的卡片
});

// 加载初始卡片
async function loadInitialCard() {
    try {
        const response = await fetch('/api/card');
        const data = await response.json();
        if (data.success && data.card) {
            state.card = data.card;
            renderEditableCard(state.card);
            updateProgress(state.card);
        } else {
            renderEditableCard(null);
        }
    } catch (error) {
        console.error('加载卡片失败:', error);
        renderEditableCard(null);
    }
}

// 事件监听
function initEventListeners() {
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.messageInput.addEventListener('keydown', handleKeyDown);
    elements.newChatBtn.addEventListener('click', startNewChat);
    if (elements.copyCardBtn) elements.copyCardBtn.addEventListener('click', copyCard);
    if (elements.saveCardBtn) elements.saveCardBtn.addEventListener('click', saveCard);
    if (elements.exportJsonBtn) elements.exportJsonBtn.addEventListener('click', exportAsJson);
}

// 自动调整文本框高度
function autoResizeTextarea() {
    elements.messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
}

// 处理键盘事件
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// 发送消息
async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message || state.isLoading) return;

    state.isLoading = true;
    elements.sendBtn.disabled = true;

    addMessage('user', message);
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';

    const loadingMsg = addMessage('assistant', '<span class="loading"><span></span><span></span><span></span></span>');

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();
        loadingMsg.remove();

        if (data.success) {
            if (data.type === 'card') {
                state.card = data.card;
                renderEditableCard(state.card);
                addMessage('assistant', '✨ ' + data.message);
            } else {
                addMessage('assistant', data.message);
            }

            if (data.state && data.state.card) {
                state.card = data.state.card;
                renderEditableCard(state.card);
                updateProgress(data.state.card);
            }
        } else {
            addMessage('assistant', '❌ 出错了：' + (data.error || '未知错误'));
        }
    } catch (error) {
        loadingMsg.remove();
        addMessage('assistant', '❌ 网络错误，请重试');
        console.error('Error:', error);
    } finally {
        state.isLoading = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    }
}

// 添加消息
function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    const avatar = role === 'user' ? '👤' : '🤖';
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-text">${content}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    elements.messages.appendChild(messageDiv);
    elements.messages.scrollTop = elements.messages.scrollHeight;
    return messageDiv;
}

// 更新进度指示器
function updateProgress(card) {
    if (!card) return;
    elements.progressIndicator.style.display = 'block';

    const fields = ['requirement_type', 'style', 'dimensions', 'layering_requirements', 'spine_reserved', 'delivery_time'];
    const items = elements.progressIndicator.querySelectorAll('.progress-item');
    for (let i = 0; i < items.length; i++) {
        const field = fields[i];
        const value = card[field];
        const isCompleted = value && value !== '待确认' && value !== '';
        if (isCompleted) {
            items[i].classList.add('completed');
            items[i].querySelector('.progress-icon').textContent = '✓';
        } else {
            items[i].classList.remove('completed');
            items[i].querySelector('.progress-icon').textContent = '⚪';
        }
    }
}

// 渲染可编辑卡片
function renderEditableCard(card) {
    if (!card) {
        // 空卡片占位
        elements.cardContent.innerHTML = `
            <div class="requirement-card editable-card">
                <div class="card-field">
                    <div class="card-field-label">需求ID</div>
                    <div class="card-field-value">--</div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">类型</div>
                    <div class="card-field-value"><input type="text" placeholder="例如：角色皮肤" id="edit_requirement_type"></div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">风格</div>
                    <div class="card-field-value"><input type="text" placeholder="例如：甜美、暗黑" id="edit_style"></div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">尺寸</div>
                    <div class="card-field-value"><input type="text" placeholder="例如：1024x1024" id="edit_dimensions"></div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">分层要求</div>
                    <div class="card-field-value"><textarea rows="2" placeholder="PSD分层要求等" id="edit_layering_requirements"></textarea></div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">Spine预留</div>
                    <div class="card-field-value"><input type="text" placeholder="需要/不需要 具体说明" id="edit_spine_reserved"></div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">交付时间</div>
                    <div class="card-field-value"><input type="text" placeholder="例如：下周五" id="edit_delivery_time"></div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">参考图</div>
                    <div class="card-field-value"><textarea rows="2" placeholder="多个链接用逗号或换行分隔" id="edit_reference_images"></textarea></div>
                </div>
                <div class="card-field">
                    <div class="card-field-label">需求描述</div>
                    <div class="card-field-value"><textarea rows="3" placeholder="详细描述需求" id="edit_description"></textarea></div>
                </div>
                <div class="card-meta">
                    <span>创建于 ${card?.created_at || new Date().toLocaleString('zh-CN')}</span>
                    <span class="card-status pending">⏳ 待完善</span>
                </div>
            </div>
        `;
        return;
    }

    let refImagesStr = '';
    if (card.reference_images && card.reference_images.length) {
        refImagesStr = card.reference_images.join('\n');
    }

    const statusClass = card.status === '已完成' ? 'complete' : 'pending';
    const statusText = card.status === '已完成' ? '✓ 已完成' : '⏳ 待完善';

    const html = `
        <div class="requirement-card editable-card">
            <div class="card-field">
                <div class="card-field-label">需求ID</div>
                <div class="card-field-value">${escapeHtml(card.requirement_id || '--')}</div>
            </div>
            <div class="card-field">
                <div class="card-field-label">类型</div>
                <div class="card-field-value"><input type="text" value="${escapeHtml(card.requirement_type || '')}" placeholder="角色皮肤/UI图标/关卡元素/推广素材" id="edit_requirement_type"></div>
            </div>
            <div class="card-field">
                <div class="card-field-label">风格</div>
                <div class="card-field-value"><input type="text" value="${escapeHtml(card.style || '')}" placeholder="甜美、暗黑、赛博、国风..." id="edit_style"></div>
            </div>
            <div class="card-field">
                <div class="card-field-label">尺寸</div>
                <div class="card-field-value"><input type="text" value="${escapeHtml(card.dimensions || '')}" placeholder="例如：1024x1024" id="edit_dimensions"></div>
            </div>
            <div class="card-field">
                <div class="card-field-label">分层要求</div>
                <div class="card-field-value"><textarea rows="2" placeholder="PSD分层要求等" id="edit_layering_requirements">${escapeHtml(card.layering_requirements || '')}</textarea></div>
            </div>
            <div class="card-field">
                <div class="card-field-label">Spine预留</div>
                <div class="card-field-value"><input type="text" value="${escapeHtml(card.spine_reserved || '')}" placeholder="需要/不需要 具体说明" id="edit_spine_reserved"></div>
            </div>
            <div class="card-field">
                <div class="card-field-label">交付时间</div>
                <div class="card-field-value"><input type="text" value="${escapeHtml(card.delivery_time || '')}" placeholder="例如：下周五" id="edit_delivery_time"></div>
            </div>
            <div class="card-field">
                <div class="card-field-label">参考图</div>
                <div class="card-field-value"><textarea rows="2" placeholder="多个链接每行一个或用逗号分隔" id="edit_reference_images">${escapeHtml(refImagesStr)}</textarea></div>
            </div>
            <div class="card-field">
                <div class="card-field-label">需求描述</div>
                <div class="card-field-value"><textarea rows="3" placeholder="详细描述需求" id="edit_description">${escapeHtml(card.description || '')}</textarea></div>
            </div>
            <div class="card-meta">
                <span>创建于 ${escapeHtml(card.created_at || new Date().toLocaleString('zh-CN'))}</span>
                <span class="card-status ${statusClass}">${statusText}</span>
            </div>
        </div>
    `;
    elements.cardContent.innerHTML = html;
}

// 保存卡片修改到后端
async function saveCard() {
    if (!elements.cardContent) return;

    const getVal = (id) => {
        const el = document.getElementById(id);
        return el ? el.value : '';
    };

    const updates = {
        requirement_type: getVal('edit_requirement_type'),
        style: getVal('edit_style'),
        dimensions: getVal('edit_dimensions'),
        layering_requirements: getVal('edit_layering_requirements'),
        spine_reserved: getVal('edit_spine_reserved'),
        delivery_time: getVal('edit_delivery_time'),
        reference_images: getVal('edit_reference_images'),
        description: getVal('edit_description')
    };

    const saveBtn = elements.saveCardBtn;
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '💾 保存中...';
    saveBtn.disabled = true;

    try {
        const response = await fetch('/api/update_card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ updates: updates })
        });
        const data = await response.json();
        if (data.success) {
            state.card = data.card;
            renderEditableCard(state.card);
            updateProgress(state.card);
            showTemporaryMessage('✅ 卡片已保存', 2000);
        } else {
            showTemporaryMessage('❌ 保存失败: ' + (data.error || '未知错误'), 3000);
        }
    } catch (error) {
        console.error('保存卡片失败:', error);
        showTemporaryMessage('❌ 网络错误，保存失败', 3000);
    } finally {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    }
}

// 导出JSON文件到本地
function exportAsJson() {
    if (!state.card) {
        showTemporaryMessage('暂无卡片数据', 1500);
        return;
    }
    const dataStr = JSON.stringify(state.card, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `requirement_${state.card.requirement_id || 'card'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showTemporaryMessage('✅ JSON文件已导出', 2000);
}

// 复制卡片内容到剪贴板
function copyCard() {
    if (!state.card) {
        showTemporaryMessage('暂无卡片数据', 1500);
        return;
    }
    const card = state.card;
    const refs = card.reference_images && card.reference_images.length ? card.reference_images.join(', ') : '无';
    const cardText = `
需求ID: ${card.requirement_id}
类型: ${card.requirement_type}
风格: ${card.style}
尺寸: ${card.dimensions}
分层要求: ${card.layering_requirements}
Spine预留: ${card.spine_reserved}
交付时间: ${card.delivery_time}
参考图: ${refs}
描述: ${card.description}
    `.trim();

    navigator.clipboard.writeText(cardText).then(() => {
        showTemporaryMessage('✓ 已复制到剪贴板', 1500);
    }).catch(err => {
        console.error('复制失败:', err);
        showTemporaryMessage('复制失败', 1500);
    });
}

// 开始新对话
async function startNewChat() {
    try {
        await fetch('/api/reset', { method: 'POST' });
        location.reload();
    } catch (error) {
        console.error('重置失败:', error);
        location.reload();
    }
}

// 显示临时提示
function showTemporaryMessage(msg, duration) {
    const toast = document.createElement('div');
    toast.className = 'toast-message';
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, duration);
}

// 辅助函数：防XSS
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}
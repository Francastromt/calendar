const API_URL = "http://localhost:8000/api";

// DOM Elements
const obligationsList = document.getElementById('obligations-list');
const clientsListEl = document.getElementById('clients-list');
const pdfInput = document.getElementById('pdf-upload');
const loadingOverlay = document.getElementById('loading');

const filterSearch = document.getElementById('filter-search');
const filterStatus = document.getElementById('filter-status');
const filterTime = document.getElementById('filter-time');

let allObligations = [];

async function fetchDashboard() {
    try {
        const res = await fetch(`${API_URL}/dashboard`);
        const data = await res.json();
        allObligations = data; // Store raw
        applyFilters();
        renderKPIs(data);
        renderCalendar(); // Update calendar
    } catch (e) {
        console.error("Error fetching dashboard:", e);
    }
}

async function fetchClients() {
    try {
        const res = await fetch(`${API_URL}/clients`);
        const data = await res.json();
        clientsListEl.innerHTML = data.map(c => `
            <li class="flex justify-between p-3 bg-slate-50 rounded border border-slate-200 text-sm">
                <span class="font-bold text-slate-700">${c.name}</span>
                <span class="font-mono text-slate-500">${c.cuit}</span>
            </li>
        `).join('');
    } catch (e) {
        console.error("Error fetching clients", e);
    }
}

function applyFilters() {
    const search = filterSearch.value.toLowerCase();
    const status = filterStatus.value;
    const time = filterTime.value;

    const now = new Date();
    const startOfWeek = new Date(now.setDate(now.getDate() - now.getDay()));
    const endOfWeek = new Date(now.setDate(now.getDate() - now.getDay() + 6));

    const filtered = allObligations.filter(item => {
        // Search
        const matchSearch = item.client_name.toLowerCase().includes(search) || item.cuit.includes(search);
        if (!matchSearch) return false;

        // Status & Late Logic
        const isLate = new Date(item.due_date) < new Date() && item.status === 'Pending';
        if (status === 'presented' && item.status !== 'Presented') return false;
        if (status === 'pending' && item.status !== 'Pending') return false;
        if (status === 'late' && !isLate) return false;

        // Time
        const due = new Date(item.due_date);
        if (time === 'week') {
            // Simple check: is within next 7 days? or calendar week?
            // Let's use "Next 7 days" for utility
            const diffTime = due - new Date();
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            if (diffDays < 0 || diffDays > 7) return false;
        }
        if (time === 'month') {
            if (due.getMonth() !== new Date().getMonth()) return false;
        }

        return true;
    });

    renderObligations(filtered);
}

// Add Listeners
filterSearch.addEventListener('input', applyFilters);
filterStatus.addEventListener('change', applyFilters);
filterTime.addEventListener('change', applyFilters);

function renderKPIs(data) {
    const pending = data.filter(d => d.status === 'Pending').length;
    const done = data.filter(d => d.status === 'Presented').length;

    document.getElementById('kpi-pending-count').textContent = pending;
    document.getElementById('kpi-done-count').textContent = done;

    // Nearest pending date
    const next = data.filter(d => d.status === 'Pending').sort((a, b) => new Date(a.due_date) - new Date(b.due_date))[0];
    if (next) {
        const d = new Date(next.due_date);
        document.getElementById('kpi-next-date').textContent = `${d.getDate()}/${d.getMonth() + 1}`;
    } else {
        document.getElementById('kpi-next-date').textContent = "--";
    }
}

function renderObligations(data) {
    if (data.length === 0) {
        obligationsList.innerHTML = `<tr><td colspan="6" class="p-8 text-center text-slate-400 italic">No se encontraron resultados.</td></tr>`;
        return;
    }

    obligationsList.innerHTML = data.map(item => {
        const isLate = new Date(item.due_date) < new Date() && item.status === 'Pending';
        const isDone = item.status === 'Presented';

        let statusBadge = '';
        if (isDone) statusBadge = `<span class="bg-green-100 text-green-700 px-2 py-1 rounded-full text-xs font-bold border border-green-200">Presentado</span>`;
        else if (isLate) statusBadge = `<span class="bg-red-100 text-red-700 px-2 py-1 rounded-full text-xs font-bold border border-red-200">Vencido</span>`;
        else statusBadge = `<span class="bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full text-xs font-bold border border-yellow-200">Pendiente</span>`;

        return `
            <tr class="hover:bg-slate-50 transition group">
                <td class="p-4 font-mono font-bold ${isLate ? 'text-red-500' : 'text-slate-700'}">
                    ${new Date(item.due_date).toLocaleDateString('es-AR')}
                </td>
                <td class="p-4 font-bold text-slate-700">${item.client_name}</td>
                <td class="p-4 text-xs text-slate-500">${item.client_type || 'RI'}</td>
                <td class="p-4">
                    <span class="bg-blue-50 text-blue-600 px-2 py-1 rounded text-xs font-bold border border-blue-100">${item.tax_name || 'IVA'}</span>
                </td>
                <td class="p-4 font-mono text-slate-500 text-xs">${item.cuit}</td>
                <td class="p-4 text-slate-600">${item.period}</td>
                <td class="p-4">${statusBadge}</td>
                <td class="p-4 text-right">
                    <button onclick="toggleStatus(${item.id})" class="text-xs font-bold px-3 py-1 rounded border transition ${isDone ? 'border-slate-300 text-slate-400 hover:bg-slate-100' : 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700 shadow-sm'}">
                        ${isDone ? 'Marcar Pendiente' : '✅ Marcar Presentado'}
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function toggleStatus(id) {
    try {
        await fetch(`${API_URL}/obligations/${id}/toggle`, { method: 'POST' });
        fetchDashboard(); // Refresh
    } catch (e) {
        alert("Error actualizando estado");
    }
}

// Upload Handler
pdfInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    loadingOverlay.classList.remove('hidden');
    loadingOverlay.classList.add('flex');

    try {
        const res = await fetch(`${API_URL}/upload-calendar`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error("Upload failed");

        const result = await res.json();
        alert(`¡Éxito! Se procesó el calendario. Reglas creadas: ${result.rules_created}`);
        fetchDashboard();

    } catch (e) {
        alert("Error al procesar el PDF: " + e.message);
    } finally {
        loadingOverlay.classList.add('hidden');
        loadingOverlay.classList.remove('flex');
        pdfInput.value = ''; // Reset
    }
});

// Excel Upload Handler
const excelInput = document.getElementById('excel-upload');
excelInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    // Use same loading spinner
    loadingOverlay.querySelector('p').innerText = "Procesando Clientes...";
    loadingOverlay.classList.remove('hidden');
    loadingOverlay.classList.add('flex');

    try {
        const res = await fetch(`${API_URL}/upload-clients`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error("Upload failed");

        const result = await res.json();
        alert(`¡Clientes Cargados! \nNuevos: ${result.created}\nActualizados: ${result.updated}`);
        fetchClients(); // Refresh list
        fetchDashboard(); // Refresh table names/types

    } catch (e) {
        alert("Error al procesar el Excel: " + e.message);
    } finally {
        loadingOverlay.classList.add('hidden');
        loadingOverlay.classList.remove('flex');
        loadingOverlay.querySelector('p').innerText = "Procesando PDF..."; // Reset text
        excelInput.value = '';
    }
});

// --- CALENDAR LOGIC ---
let currentDate = new Date(); // To track current displayed month

function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    const title = document.getElementById('calendar-title');
    if (!grid || !title) return;

    grid.innerHTML = '';

    // Set Header
    const monthNames = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
    title.innerText = `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;

    // Calculate Days
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const firstDay = new Date(year, month, 1).getDay(); // 0 = Sunday
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    // Empty Cells before 1st
    for (let i = 0; i < firstDay; i++) {
        const empty = document.createElement('div');
        empty.className = "bg-slate-50/50 rounded-xl";
        grid.appendChild(empty);
    }

    // Day Cells
    for (let i = 1; i <= daysInMonth; i++) {
        const cell = document.createElement('div');
        cell.className = "bg-white border border-slate-100 rounded-xl p-2 flex flex-col gap-1 transition-all hover:shadow-md hover:border-indigo-200 relative group overflow-hidden cursor-pointer";

        // Date Number
        const currentDayStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;

        const isToday = (new Date().toISOString().split('T')[0] === currentDayStr);
        const dayNumClass = isToday ? "bg-indigo-600 text-white w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold" : "text-slate-400 text-xs font-bold";

        cell.innerHTML = `<div class="${dayNumClass}">${i}</div>`;

        // Find Obligations for this day
        if (typeof allObligations !== 'undefined') {
            const daysObs = allObligations.filter(ob => ob.due_date === currentDayStr);

            // Add click handler for the whole cell if there are obligations
            if (daysObs.length > 0) {
                cell.onclick = () => openDayModal(currentDayStr, daysObs);

                // Render 2-3 pills max for preview
                daysObs.slice(0, 3).forEach(ob => {
                    const taxColor = ob.tax_name === 'IVA' ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700';
                    const pill = document.createElement('div');
                    pill.className = `text-[10px] ${taxColor} px-1.5 py-0.5 rounded font-bold truncate`;
                    pill.innerText = `${ob.tax_name} - ${ob.client_name}`;
                    cell.appendChild(pill);
                });

                if (daysObs.length > 3) {
                    const more = document.createElement('div');
                    more.className = "text-[10px] text-slate-400 font-medium pl-1";
                    more.innerText = `+${daysObs.length - 3} más...`;
                    cell.appendChild(more);
                }
            }
        }

        grid.appendChild(cell);
    }
}

function openDayModal(dateStr, obligations) {
    const modal = document.getElementById('day-modal');
    const title = document.getElementById('day-modal-title');
    const content = document.getElementById('day-modal-content');

    // Format Date
    const [y, m, d] = dateStr.split('-');
    title.innerText = `Vencimientos del ${d}/${m}`;

    content.innerHTML = obligations.map(ob => {
        const isDone = ob.status === 'Presented';
        return `
            <div class="flex items-center justify-between p-3 border-b border-slate-50 hover:bg-slate-50 rounded-lg group transition">
                <div class="flex flex-col">
                    <span class="font-bold text-slate-700 text-sm">${ob.client_name}</span>
                    <div class="flex gap-2 items-center">
                        <span class="text-xs font-bold text-indigo-600 bg-indigo-50 px-1.5 rounded">${ob.tax_name}</span>
                        <span class="text-xs text-slate-400">${ob.cuit}</span>
                    </div>
                </div>
                 <button onclick="toggleStatus(${ob.id}); closeDayModal();" 
                    class="text-xs px-3 py-1 rounded-full font-bold transition ${isDone ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500 group-hover:bg-blue-600 group-hover:text-white'}">
                    ${isDone ? 'OK' : 'Marcar'}
                 </button>
            </div>
         `;
    }).join('');

    modal.classList.remove('hidden');
}

function closeDayModal() {
    document.getElementById('day-modal').classList.add('hidden');
}

function changeMonth(delta) {
    currentDate.setMonth(currentDate.getMonth() + delta);
    renderCalendar();
}

// Tab Switching
const tabList = document.getElementById('tab-list');
const tabCalendar = document.getElementById('tab-calendar');
const viewList = document.getElementById('view-list');
const viewCalendar = document.getElementById('view-calendar');

if (tabList && tabCalendar) {
    tabList.addEventListener('click', () => {
        // Style Active
        tabList.classList.add('border-indigo-600', 'text-indigo-600');
        tabList.classList.remove('border-transparent', 'text-slate-500');
        tabCalendar.classList.add('border-transparent', 'text-slate-500');
        tabCalendar.classList.remove('border-indigo-600', 'text-indigo-600');

        // View
        viewList.classList.remove('hidden');
        viewCalendar.classList.add('hidden');
    });

    tabCalendar.addEventListener('click', () => {
        // Style Active
        tabCalendar.classList.add('border-indigo-600', 'text-indigo-600');
        tabCalendar.classList.remove('border-transparent', 'text-slate-500');
        tabList.classList.add('border-transparent', 'text-slate-500');
        tabList.classList.remove('border-indigo-600', 'text-indigo-600');

        // View
        viewCalendar.classList.remove('hidden');
        viewList.classList.add('hidden');

        renderCalendar(); // Render on switch
    });
}

// Init
fetchClients();
fetchDashboard();

// Chat Logic
const chatToggle = document.getElementById('chat-toggle');
const chatWindow = document.getElementById('chat-window');
const closeChat = document.getElementById('close-chat');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');

function toggleChat() {
    chatWindow.classList.toggle('hidden');
}

chatToggle.addEventListener('click', toggleChat);
closeChat.addEventListener('click', toggleChat);

function appendMessage(text, isUser) {
    const div = document.createElement('div');
    div.className = isUser
        ? "bg-slate-200 text-slate-800 p-2 rounded-lg rounded-tr-none self-end max-w-[85%] ml-auto"
        : "bg-blue-100 text-blue-800 p-2 rounded-lg rounded-tl-none self-start max-w-[85%]";
    div.innerText = text; // dangerous innerText is safer than innerHTML for user input
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return; // Keep this check

    // Add user message
    const div = document.createElement('div');
    div.className = "bg-indigo-600 text-white p-3 rounded-2xl rounded-br-none self-end max-w-[85%] shadow-md text-sm whitespace-pre-wrap";
    div.innerText = text;
    chatMessages.appendChild(div);

    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Loading
    const loadingDiv = document.createElement('div');
    loadingDiv.className = "flex gap-2 p-3 bg-slate-100 rounded-2xl rounded-tl-none self-start items-center";
    loadingDiv.innerHTML = `<div class="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div><div class="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></div><div class="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></div>`;
    loadingDiv.id = "chat-loading";
    chatMessages.appendChild(loadingDiv);

    // Generate AI response
    try {
        const res = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        if (!res.ok) throw new Error("Server Error");

        const data = await res.json();

        // Remove loading
        chatMessages.removeChild(loadingDiv);

        appendMessage('ai', data.response);

    } catch (e) {
        chatMessages.removeChild(loadingDiv);
        appendMessage('ai', "Error conectando con el asistente.");
    }
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

function appendMessage(sender, text) {
    const div = document.createElement('div');

    if (sender === 'user') {
        div.className = "bg-indigo-600 text-white p-3 rounded-2xl rounded-br-none self-end max-w-[85%] shadow-md text-sm whitespace-pre-wrap";
        div.innerText = text;
    } else {
        div.className = "flex gap-3";
        div.innerHTML = `
            <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 flex-shrink-0 mt-1">
                <i class="fas fa-robot text-xs"></i>
            </div>
            <div class="bg-white text-slate-700 p-3 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 max-w-[85%] text-sm whitespace-pre-wrap font-medium"></div>
        `;
        // Securely set text content to avoid HTML injection and ensure formatting
        div.querySelector('.bg-white').innerText = text;
    }

    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

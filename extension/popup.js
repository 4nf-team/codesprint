// Ждем, пока весь HTML точно загрузится
document.addEventListener('DOMContentLoaded', async () => {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('imageInput');
  const resultBox = document.getElementById('resultBox');
  const statusSpan = document.getElementById('status');
  const explanationText = document.getElementById('explanation');
  const loginBtn = document.getElementById('loginBtn');
  const authStatus = document.getElementById('authStatus');

  // Проверяем статус аутентификации при загрузке
  checkAuth();

  // 1. КНОПКА АВТОРИЗАЦИИ
  loginBtn?.addEventListener('click', async () => {
    authStatus.textContent = 'Opening Telegram auth...';
    try {
      const response = await chrome.runtime.sendMessage({ action: 'loginWithTelegram' });
      if (response.status === 'opened') {
        authStatus.textContent = 'Auth page opened. Complete login in the new tab.';
      }
    } catch (error) {
      authStatus.textContent = 'Error: ' + error.message;
    }
  });

  // Функция проверки аутентификации
  async function checkAuth() {
    try {
      const response = await chrome.runtime.sendMessage({ action: 'checkAuth' });
      if (response.authenticated) {
        authStatus.textContent = '✓ Authenticated';
        authStatus.style.color = '#4cff4c';
        loginBtn.style.display = 'none';
      } else {
        authStatus.textContent = 'Not authenticated';
        authStatus.style.color = '#ff4c4c';
        loginBtn.style.display = 'inline-block';
      }
    } catch (error) {
      console.error('Auth check failed:', error);
    }
  }

  // 2. ЖЕСТКАЯ БЛОКИРОВКА открытия картинки в браузере
  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    document.addEventListener(eventName, preventDefaults, false);
  });

  // 3. Починка клика: теперь инпут точно сработает
  dropZone.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', function() {
    if (this.files && this.files.length > 0) {
      handleFile(this.files[0]);
    }
  });

  // 4. Визуальные эффекты при перетаскивании
  dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

  // 5. Ловим сам файл, когда его бросили
  dropZone.addEventListener('drop', (e) => {
    dropZone.classList.remove('dragover');
    let dt = e.dataTransfer;
    let files = dt.files;
    
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  });

  // 6. Отправка на бэкенд
  async function handleFile(file) {
    dropZone.innerHTML = '<span style="font-size: 24px; display: block; margin-bottom: 8px;">🖼️</span><strong>Selected:</strong><br>' + file.name;
    
    const formData = new FormData();
    formData.append("file", file);

    resultBox.style.display = "block";
    statusSpan.textContent = "Analyzing...";
    statusSpan.style.color = "#e0e0e0";
    explanationText.textContent = "";

    try {
      // Получаем токен из storage
      const result = await chrome.storage.local.get(['access_token']);
      const token = result.access_token;
      
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        body: formData,
        headers: headers
      });

      if (!response.ok) throw new Error("Server error");

      const data = await response.json();
      
      if (data.is_fake) {
          statusSpan.textContent = "Fake Detected 🚨";
          statusSpan.style.color = "#ff4c4c";
      } else {
          statusSpan.textContent = "Looks Real ✅";
          statusSpan.style.color = "#4cff4c";
      }
      explanationText.textContent = data.explanation;

    } catch (error) {
      statusSpan.textContent = "Error ❌";
      statusSpan.style.color = "#ff4c4c";
      explanationText.textContent = "Could not connect to backend. Is FastAPI running?";
      console.error("Error:", error);
    }
  }
});
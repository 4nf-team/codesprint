// Content Script для страницы аутентификации Telegram
// Автоматически извлекает токен из URL и отправляет в background

(function() {
  // Проверяем, есть ли токен в URL (например, ?token=...)
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token') || urlParams.get('access_token');
  
  if (token) {
    // Отправляем токен в background script для сохранения
    chrome.runtime.sendMessage({
      action: 'saveToken',
      token: token
    });
  }
  
  // Также можно искать токен в DOM, если backend встраивает его в страницу
  // Например, в элементе с id="token" или в JSON-скрипте
  const tokenElement = document.getElementById('token');
  if (tokenElement) {
    const tokenFromDom = tokenElement.textContent || tokenElement.value;
    if (tokenFromDom) {
      chrome.runtime.sendMessage({
        action: 'saveToken',
        token: tokenFromDom.trim()
      });
    }
  }
})();

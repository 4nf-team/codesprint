// Background Service Worker для Manifest V3
// Обрабатывает клик по иконке и управляет аутентификацией

// Открываем popup при клике на иконку (это и так делает default_popup, но оставим для совместимости)
chrome.action.onClicked.addListener(() => {
  // default_popup уже открывается автоматически, этот обработчик не нужен
});

// Слушаем сообщения от popup для аутентификации
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'loginWithTelegram') {
    // Открываем страницу аутентификации в новой вкладке
    chrome.tabs.create({ url: 'http://127.0.0.1:8000/telegram/telegram/' });
    sendResponse({ status: 'opened' });
  }
  
  if (request.action === 'checkAuth') {
    // Проверяем, есть ли токен в storage
    chrome.storage.local.get(['access_token'], (result) => {
      sendResponse({ authenticated: !!result.access_token });
    });
    // Возвращаем true, чтобы показать, что мы будем отвечать асинхронно
    return true;
  }
  
  if (request.action === 'storeToken') {
    // Сохраняем токен (приходит от страницы аутентификации через content script или напрямую)
    chrome.storage.local.set({ access_token: request.token }, () => {
      sendResponse({ status: 'saved' });
    });
    return true;
  }
});

// Слушаем сообщения от content script на странице аутентификации
// (если backend перенаправляет на страницу, где можно извлечь токен)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'saveToken' && request.token) {
    chrome.storage.local.set({ access_token: request.token });
    sendResponse({ status: 'saved' });
    // Закрываем вкладку аутентификации
    if (sender.tab?.id) {
      chrome.tabs.remove(sender.tab.id);
    }
  }
});

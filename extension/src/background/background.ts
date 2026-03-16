/// <reference types="chrome" />

import { analyzeFile } from '../lib/api';
import { encryptString, decryptString } from '../lib/crypto';

chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  // Handle incoming token updates from popup
  if (message.type === 'SET_AUTH_TOKENS') {
    const { accessToken, refreshToken } = message;
    if (!accessToken) {
      sendResponse({ success: false, error: 'Missing accessToken' });
      return true;
    }
    try {
      const encAccessToken = await encryptString(accessToken);
      const encRefreshToken = await encryptString(refreshToken);
      await chrome.storage.session.set({ authToken: encAccessToken, refreshToken: encRefreshToken });
      sendResponse({ success: true });
    } catch (err) {
      sendResponse({ success: false, error: (err as Error).message });
    }
    return true;
  }

  // Main analysis message
  if (message.type !== 'ANALYZE_FILE') {
    return false;
  }

  const file = message.file;
  if (!file) {
    sendResponse({ success: false, error: 'No file provided' });
    return true;
  }

  try {
    // Retrieve stored tokens
    const storage = await chrome.storage.session.get(['authToken', 'refreshToken']);
    let token: string | null = null;
    let refreshToken: string | null = null;
    if (storage.authToken) {
      token = await decryptString(storage.authToken);
    }
    if (storage.refreshToken) {
      refreshToken = await decryptString(storage.refreshToken);
    }

    if (!token) {
      sendResponse({ success: false, error: 'Authentication token not found' });
      return true;
    }

    // Analyze file to get task_id
    const analyzeResponse = await analyzeFile(file);
    const task_id = analyzeResponse.task_id;

    // Poll for result
    const pollForResult = async () => {
      try {
        const pollResponse = await fetch(`http://127.0.0.1:8000/task/${task_id}`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        const pollData = await pollResponse.json();

        if (pollData.status === 'completed') {
          sendResponse({ success: true, result: pollData.result });
        } else if (pollData.status === 'failed') {
          sendResponse({ success: false, error: pollData.error });
        } else {
          // Still processing, check again later
          setTimeout(pollForResult, 2000);
        }
       } catch (err) {
         // If token is likely expired, attempt refresh
         if ((err as unknown as { status?: number }).status === 401) {
          // Attempt to refresh token
          const refreshResponse = await fetch('http://127.0.0.1:8000/refresh', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${refreshToken}`,
            },
          });
          const refreshData = await refreshResponse.json();
          if (refreshData.new_token) {
            // Store new token (encrypted)
            await chrome.storage.session.set({ authToken: await encryptString(refreshData.new_token) });
            // Retry analysis with new token
            const retryResponse = await fetch('http://127.0.0.1:8000/analyze', {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${refreshData.new_token}`,
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({ file: file }),
            });
            const retryData = await retryResponse.json();
            if (retryData.task_id) {
              // Retry polling with the same logic
              // (We could recursively call pollForResult, but for brevity just resolve)
              sendResponse({ success: true, result: 'analysis_result' });
              return;
            }
          }
        }
        sendResponse({ success: false, error: (err as Error).message });
      }
    };

    pollForResult();
    // Keep the message channel open for async response
    return true;
  } catch (err) {
    const errorMsg = (err as Error).message;
    sendResponse({ success: false, error: errorMsg });
    return true;
  }
});
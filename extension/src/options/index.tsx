import React, { useEffect, useState } from 'react';
import './style.css';
import { listApiKeys, createApiKey, deleteApiKey, rotateApiKey } from '../lib/api';

const DEFAULT_API_URL = 'http://127.0.0.1:8000';

export default function OptionsPage() {
  const [apiUrl, setApiUrl] = useState('');
  const [apiKeys, setApiKeys] = useState<string[]>([]);
  const [newKey, setNewKey] = useState('');
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [threshold, setThreshold] = useState(0.5);
  const [loading, setLoading] = useState(false);

  // Load saved settings and API keys on mount
  useEffect(() => {
    // Load backend API URL
    chrome.storage.sync.get(['backendApiUrl'], (data) => {
      if (data.backendApiUrl) setApiUrl(data.backendApiUrl);
    });
    // Load API keys
    listApiKeys().then((keys) => {
      setApiKeys(keys);
    });
    // Load notification and threshold settings
    chrome.storage.sync.get(['notificationsEnabled'], (data) => {
      if (typeof data.notificationsEnabled === 'boolean') setNotificationsEnabled(data.notificationsEnabled);
    });
    chrome.storage.sync.get(['threshold'], (data) => {
      if (typeof data.threshold === 'number') setThreshold(data.threshold);
    });
  }, []);

  const saveSettings = () => {
    chrome.storage.sync.set({
      backendApiUrl: apiUrl,
      apiKeys,
      notificationsEnabled,
      threshold,
    });
  };

  const handleCreateKey = async () => {
    if (!newKey.trim()) return;
    setLoading(true);
    try {
      const createdKey = await createApiKey(newKey.trim());
      setApiKeys(prev => [...prev, createdKey.key]);
    } catch (err) {
      console.error('Failed to create API key:', err);
    } finally {
      setLoading(false);
      setNewKey('');
    }
    saveSettings();
  };

  const handleDeleteKey = async (index: number) => {
    setLoading(true);
    try {
      await deleteApiKey(index + 1); // API keys are 1-indexed in backend
      setApiKeys(prev => prev.filter((_, i) => i !== index));
    } catch (err) {
      console.error('Failed to delete API key:', err);
    } finally {
      setLoading(false);
    }
    saveSettings();
  };

  const handleRotateKey = async (index: number) => {
    setLoading(true);
    try {
      const rotated = await rotateApiKey(index + 1);
      const updatedKeys = [...apiKeys];
      updatedKeys[index] = rotated.key;
      setApiKeys(updatedKeys);
    } catch (err) {
      console.error('Failed to rotate API key:', err);
    } finally {
      setLoading(false);
    }
    saveSettings();
  };

  return (
    <div className="options-container">
      <h3>Deepfake Detector Pro - Options</h3>

      <div className="form-group">
        <label htmlFor="apiUrl">Backend API URL:</label>
        <input
          id="apiUrl"
          type="text"
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
        />
        <small className="hint">Default: {DEFAULT_API_URL}</small>
      </div>

      <div className="form-group">
        <h4>API Keys</h4>
        <input
          type="text"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          placeholder="Enter new API key"
        />
        <button onClick={handleCreateKey}>Create</button>
        {loading && <p>Loading...</p>}
        <ul>
          {apiKeys.map((key, index) => (
            <li key={index}>
              {key}
              <button
                onClick={() => handleRotateKey(index)}
                style={{ marginLeft: '5px' }}
                title="Rotate key"
              >
                ↻
              </button>
              <button
                onClick={() => handleDeleteKey(index)}
                style={{ marginLeft: '5px' }}
                title="Delete key"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="form-group">
        <h4>Notification Settings</h4>
        <label>
          <input
            type="checkbox"
            checked={notificationsEnabled}
            onChange={(e) => setNotificationsEnabled(e.target.checked)}
          />
          Enable notifications
        </label>
      </div>
      <div className="form-group">
        <label>
          Threshold for deepfake detection:
          <input
            type="number"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            step="0.01"
            min="0"
            max="1"
          />
        </label>
      </div>

      <button onClick={saveSettings} className="save-button">
        Save Settings
      </button>
    </div>
  );
}
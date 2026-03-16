import React, { useState, useRef, useEffect } from 'react';
import './style.css';

interface AnalysisResponse {
  realism_percentage?: number;
  uniqueness_warning?: string;
  status?: string;
}

interface AuthData {
  method: 'apiKey' | 'telegram';
  key?: string;
  token?: string;
}

interface Message {
  action: 'analyze';
  file: {
    name: string;
    type: string;
    size: number;
    content: ArrayBuffer;
  };
  auth: AuthData;
}

const Popup: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [authMethod, setAuthMethod] = useState<'apiKey' | 'telegram'>('apiKey');
  const [apiKey, setApiKey] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [explanation, setExplanation] = useState('');
  const [realismPercentage, setRealismPercentage] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Load saved auth settings from chrome.storage.session
    chrome.storage.session.get(['authMethod', 'apiKey', 'authToken'], (result) => {
      if (result.authMethod) setAuthMethod(result.authMethod as 'apiKey' | 'telegram');
      if (result.apiKey) setApiKey(result.apiKey as string);
      if (result.authToken) setAuthToken(result.authToken as string);
    });
  }, []);

  useEffect(() => {
    // Save auth settings to chrome.storage.session whenever they change
    chrome.storage.session.set({
      authMethod,
      apiKey,
      authToken,
    });
  }, [authMethod, apiKey, authToken]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
      startAnalysis();
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files?.[0]) {
      setFile(e.dataTransfer.files[0]);
      startAnalysis();
    }
  };

  const startAnalysis = () => {
    if (!file) {
      setError('Please select a file or drop a file');
      return;
    }
    // Validate file type and size
    if (!file.type.startsWith('image/')) {
      setError('Only image files are allowed');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('File too large (max 5MB)');
      return;
    }
    setLoading(true);
    setStatus('Analyzing...');
    setExplanation('');
    setRealismPercentage(null);
    setError(null);

    const reader = new FileReader();
    reader.onloadend = () => {
      const message: Message = {
        action: 'analyze',
        file: {
          name: file.name,
          type: file.type,
          size: file.size,
          content: reader.result as ArrayBuffer,
        },
        auth: authMethod === 'telegram'
          ? { method: 'telegram', token: authToken }
          : { method: 'apiKey', key: apiKey },
      };

      chrome.runtime.sendMessage(message, (response: AnalysisResponse | undefined) => {
        setLoading(false);
        if (chrome.runtime.lastError) {
          setError((chrome.runtime.lastError.message as string) || 'Unknown error');
          setStatus('Error');
          setExplanation('');
          setRealismPercentage(null);
        } else {
          if (response) {
            setStatus(response.status ? response.status : 'Completed');
            setExplanation(response.uniqueness_warning ? response.uniqueness_warning : '');
            setRealismPercentage(response.realism_percentage ?? null);
          } else {
            setStatus('Completed');
            setExplanation('');
            setRealismPercentage(null);
          }
        }
      });
    };
    reader.readAsArrayBuffer(file);
  };

  return (
    <div>
      {/* Authentication */}
      <div className='auth-section'>
        <label>
          {authMethod === 'apiKey' ? 'API Key' : 'Telegram Bot Token'}
          <input
            type='text'
            value={authMethod === 'apiKey' ? apiKey : authToken}
            onChange={(e) => {
              if (authMethod === 'apiKey') {
                setApiKey(e.target.value as string);
              } else {
                setAuthToken(e.target.value as string);
              }
            }}
            placeholder={authMethod === 'apiKey' ? 'Enter API key' : 'Enter Telegram token'}
          />
        </label>

        <label>
          Authentication method
          <select value={authMethod} onChange={(e) => {
            setAuthMethod(e.target.value as 'apiKey' | 'telegram');
          }}>
            <option value='apiKey'>API Key</option>
            <option value='telegram'>Telegram Widget</option>
          </select>
        </label>
      </div>

      {/* Drop zone and file input */}
      <div id='dropZone' onDragOver={handleDragOver} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
        Drop image here<br/>
        or click to select
      </div>
      <input
        type='file'
        ref={fileInputRef}
        onChange={handleFileUpload}
        disabled={loading}
        accept='image/*'
      />

      {/* Loading state */}
      {loading && <p>Analyzing...</p>}

      {/* Result */}
      <div id='resultBox'>
        <strong>Status:</strong> <span id='status'>{status}</span><br/>
        {realismPercentage && <p><strong>Realism:</strong> {realismPercentage}%</p>}
        <strong>Explanation:</strong>
        <p id='explanation'>{explanation}</p>
      </div>

      {/* Error */}
      {error && <p className='error'>Error: {error}</p>}
    </div>
  );
};

export default Popup;
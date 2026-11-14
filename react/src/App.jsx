import { useEffect, useState } from 'react';
import './App.css';

function App() {
  const [backendMessage, setBackendMessage] = useState('Connecting to backend...');

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setBackendMessage(data.message))
      .catch((err) => setBackendMessage('Failed to reach backend: ' + err.message));
  }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', textAlign: 'center' }}>
      <h1> Project Nebula</h1>
      <p>
        <strong>Backend Status: </strong> 
        <span style={{ color: backendMessage.includes('Failed') ? 'red' : 'green' }}>
          {backendMessage}
        </span>
      </p>
    </div>
  );
}

export default App;
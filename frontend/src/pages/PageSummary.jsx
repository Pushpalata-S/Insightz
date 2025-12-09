import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { marked } from 'marked';
import '../index.css'; // Assuming you have global styles here

const PageSummary = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const filename = searchParams.get('file');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pages, setPages] = useState([]);

  useEffect(() => {
    if (!filename) return;

    const fetchSummary = async () => {
      try {
        const token = localStorage.getItem('ranger_token'); // Auth token
        const res = await fetch('http://127.0.0.1:8000/page-summary', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}` 
          },
          body: JSON.stringify({ filenames: [filename] }),
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        setPages(data.pages || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, [filename]);

  return (
    <div className="main" style={{ padding: '40px', maxWidth: '900px', margin: '0 auto' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', borderBottom: '1px solid #333', paddingBottom: '20px' }}>
        <h1 style={{ color: '#f1c40f', margin: 0 }}>Deep Scan: {filename}</h1>
        <button 
          onClick={() => navigate('/dashboard')} 
          style={{ background: '#333', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
        >
          ← Back to Console
        </button>
      </header>

      {/* ERROR STATE */}
      {error && (
        <div style={{ color: '#e74c3c', textAlign: 'center', padding: '20px', background: '#2c1e1e', borderRadius: '8px' }}>
          ❌ Error: {error}
        </div>
      )}

      {/* LOADING STATE */}
      {loading && (
        <div style={{ textAlign: 'center', color: '#f1c40f', marginTop: '50px' }}>
          <h2>Scanning document pages... ⏳</h2>
          <p style={{ color: '#888' }}>(This allows the AI to read every single page individually)</p>
        </div>
      )}

      {/* RESULTS */}
      {!loading && !error && (
        <div className="page-list">
          {pages.map((page) => (
            <div key={page.page} style={{ background: '#1e1e1e', border: '1px solid #333', borderRadius: '8px', padding: '25px', marginBottom: '20px' }}>
              <span style={{ color: '#f1c40f', fontWeight: 'bold', display: 'block', marginBottom: '15px', borderBottom: '1px solid #333', paddingBottom: '5px' }}>
                PAGE {page.page}
              </span>
              <div 
                className="markdown-body" 
                dangerouslySetInnerHTML={{ __html: marked.parse(page.summary) }} 
                style={{ color: '#ccc', lineHeight: '1.6' }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PageSummary;
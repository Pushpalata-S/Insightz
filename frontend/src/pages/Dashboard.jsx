import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { marked } from 'marked'; // --- IMPORT MARKED FOR PRETTY TEXT ---
import { api } from '../services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState([]);
  const [activeTab, setActiveTab] = useState('search'); 
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Features State
  const [searchContext, setSearchContext] = useState('');
  const [query, setQuery] = useState('');
  const [searchResult, setSearchResult] = useState('Ready for query.');
  const [crossResult, setCrossResult] = useState('Select files and click generate.');
  const [uploadStatus, setUploadStatus] = useState('');
  const [selectedDocs, setSelectedDocs] = useState(new Set());
  const [isDragOver, setIsDragOver] = useState(false);

  // Initial Load
  useEffect(() => {
    if (!localStorage.getItem("ranger_token")) navigate('/');
    fetchDocs();
  }, []);

  // --- REFRESH FUNCTION ---
  const fetchDocs = async () => {
    try {
      const res = await api.get('/documents');
      setDocs(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.warn("Backend offline. Switching to Simulation Mode.");
      setDocs([
        { filename: "mission_report.pdf", category: "Mission", summary: "Simulation: Mission active." },
        { filename: "tech_specs.txt", category: "Tech", summary: "Simulation: All systems nominal." },
      ]);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("ranger_token");
    navigate('/');
  };

  const handleSummaryClick = (e, summaryText) => {
    e.stopPropagation();
    alert(summaryText || "No summary available for this file.");
  };

  // --- NEW: HANDLE PAGE SUMMARY NAVIGATION ---
  const handlePageSummary = () => {
    if (selectedDocs.size === 0) return alert("Please select a file first!");
    if (selectedDocs.size > 1) return alert("For Page-Wise breakdown, please select ONLY ONE file.");
    
    // Get the single filename from the Set
    const filename = Array.from(selectedDocs)[0];
    
    // Navigate to the new page
    navigate(`/summary?file=${encodeURIComponent(filename)}`);
  };

  // --- UPLOAD FUNCTION ---
  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    setUploadStatus("Processing...");

    try {
      const res = await api.post('/upload', formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setUploadStatus(`Success! Category: ${res.data.category}`);
      fetchDocs(); 
    } catch (err) {
      if (err.response && err.response.status === 500) {
         setUploadStatus("Error: Backend API limit reached.");
      } else {
         setUploadStatus("Error uploading file.");
      }
    }
  };

  const toggleDocSelection = (filename) => {
    setSelectedDocs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(filename)) newSet.delete(filename);
      else newSet.add(filename);
      return newSet;
    });
  };

  const handleDragStart = (e, filename) => e.dataTransfer.setData("filename", filename);
  
  const handleDrop = (e, panel) => {
    e.preventDefault();
    setIsDragOver(false);
    const filename = e.dataTransfer.getData("filename");
    if (panel === 'search') setSearchContext(filename);
    else if (panel === 'cross') {
      setSelectedDocs(prev => new Set(prev).add(filename));
      setCrossResult(`[+] Added "${filename}"`);
    }
  };

  const executeSearch = async () => {
    if (!query) return setSearchResult("Please type a question.");
    setSearchResult("Searching...");
    const finalQuery = searchContext ? `Context: ${searchContext}. ${query}` : query;
    try {
      const res = await api.get(`/search?query=${encodeURIComponent(finalQuery)}`);
      // Format: Answer + Citation
      setSearchResult(`${res.data.answer}<br><br><small style="color:#888">${res.data.citation}</small>`);
    } catch (e) { setSearchResult("Error searching."); }
  };

  const executeCrossSummary = async () => {
    if (selectedDocs.size === 0) return alert("Select at least 1 document!");
    setCrossResult("Synthesizing Report...");
    try {
      const res = await api.post('/cross-summary', { filenames: Array.from(selectedDocs) });
      setCrossResult(res.data.cross_summary);
    } catch (e) { setCrossResult("Error generating report."); }
  };

  return (
    <div className="dashboard-container">
      <div className={`overlay ${sidebarOpen ? 'active' : ''}`} onClick={() => setSidebarOpen(false)}></div>

      {/* SIDEBAR */}
      <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <h2>📂 Intel Library</h2>
          <button className="mobile-toggle" onClick={() => setSidebarOpen(false)}>✕</button>
        </div>
        
        <div className="doc-list">
          {docs.length === 0 && <div style={{ color: '#666', fontStyle:'italic' }}>No docs found.</div>}
          {docs.map(doc => (
            <div 
              key={doc.filename} 
              className="doc-item"
              draggable
              onDragStart={(e) => handleDragStart(e, doc.filename)}
            >
              <input 
                type="checkbox" 
                checked={selectedDocs.has(doc.filename)}
                onChange={() => toggleDocSelection(doc.filename)}
                style={{ transform: 'scale(1.2)', marginRight: '10px', cursor:'pointer' }}
              />
              <div className="doc-info">
                <span className="doc-name" title={doc.filename}>{doc.filename}</span>
                <span className="doc-cat">{doc.category}</span>
              </div>
              <button 
                onClick={(e) => handleSummaryClick(e, doc.summary)}
                style={{ background: 'none', border: '1px solid #555', color: '#aaa', borderRadius: '4px', padding:'2px 6px' }}
                title="View Summary"
              >
                📄
              </button>
            </div>
          ))}
        </div>
        <button className="sidebar-btn btn-refresh" onClick={fetchDocs}>🔄 Refresh List</button>
        <button className="sidebar-btn btn-logout" onClick={handleLogout}>🛑 Logout</button>
      </div>

      {/* MAIN CONTENT */}
      <div className="main-content">
        <button className="mobile-toggle" onClick={() => setSidebarOpen(true)}>☰ Menu</button>

        <h1 style={{ color: 'var(--accent)', marginTop: 0 }}>⚡ Yellow Ranger Console</h1>

        <div className="upload-zone">
          <h3>⬆️ Upload New Intel</h3>
          <input type="file" onChange={handleUpload} style={{ display: 'none' }} id="file-upload" />
          <button className="action-btn" onClick={() => document.getElementById('file-upload').click()}>
            Choose File & Upload
          </button>
          <p style={{ color: '#aaa', marginTop: '10px' }}>{uploadStatus}</p>
        </div>

        <div className="tabs">
          <div className={`tab ${activeTab === 'search' ? 'active' : ''}`} onClick={() => setActiveTab('search')}>
            🔍 Semantic Search
          </div>
          <div className={`tab ${activeTab === 'cross' ? 'active' : ''}`} onClick={() => setActiveTab('cross')}>
            🔗 Intelligence Actions
          </div>
        </div>

        {activeTab === 'search' && (
          <div 
            className="panel"
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => handleDrop(e, 'search')}
            style={isDragOver ? { borderColor: 'var(--accent)', background: '#252525' } : {}}
          >
            <h3>Ask the Database</h3>
            
            <div style={{ marginBottom: '15px' }}>
              <label style={{ color:'#888', fontSize:'0.9em', display:'block', marginBottom:'5px' }}>
                Target Document (Drag file here):
              </label>
              <div style={{ display: 'flex', gap: '10px' }}>
                <input 
                  type="text" 
                  readOnly 
                  value={searchContext || "Entire Database (Global Search)"}
                  placeholder="Drag a file here to focus search..." 
                  style={{ 
                    width: '100%', padding: '12px', background: '#1a1a1a', 
                    border: '1px dashed #555', color: searchContext ? 'var(--accent)' : '#666',
                    cursor: 'default'
                  }}
                />
                {searchContext && (
                  <button 
                    onClick={() => setSearchContext('')}
                    style={{ background:'#333', color:'white', padding:'0 15px', borderRadius:'4px' }}
                  >
                    ✕ Clear
                  </button>
                )}
              </div>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ color:'#888', fontSize:'0.9em', display:'block', marginBottom:'5px' }}>
                Your Question:
              </label>
              <input 
                type="text" 
                placeholder="e.g., Summarize this document, or What is the main topic?" 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ width: '100%', padding: '12px', background: '#222', border: '1px solid #444', color: 'white' }}
                onKeyDown={(e) => e.key === 'Enter' && executeSearch()}
              />
            </div>

            <button className="action-btn" onClick={executeSearch}>Execute Search</button>
            {/* UPDATED: Markdown Support for Search */}
            <div 
                className="result-box markdown-body" 
                dangerouslySetInnerHTML={{ __html: searchResult === 'Ready for query.' || searchResult === 'Searching...' ? searchResult : marked.parse(searchResult) }}
            />
          </div>
        )}

        {activeTab === 'cross' && (
          <div 
            className="panel"
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDrop={(e) => handleDrop(e, 'cross')}
          >
            <h3>Connect Intelligence</h3>
            <p>Select documents from the Sidebar list to perform actions.</p>
            
            {/* BUTTONS CONTAINER */}
            <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
              
              {/* BUTTON 1: CROSS SUMMARY */}
              <button className="action-btn" onClick={executeCrossSummary}>
                Generate Connection Report
              </button>

              {/* BUTTON 2: PAGE WISE SUMMARY (Already correctly added in your code) */}
              <button 
                className="action-btn" 
                onClick={handlePageSummary}
                style={{ background: '#2980b9' }} 
              >
                📄 View Page-Wise Breakdown
              </button>
            </div>

            {/* UPDATED: Markdown Support for Cross-Summary */}
            <div 
                className="result-box markdown-body" 
                dangerouslySetInnerHTML={{ __html: crossResult.includes('Select files') || crossResult.includes('Synthesizing') || crossResult.includes('[+]') ? crossResult : marked.parse(crossResult) }}
            />
          </div>
        )}
      </div>
    </div>
  );
}





// import { useState, useEffect } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { api } from '../services/api';

// export default function Dashboard() {
//   const navigate = useNavigate();
//   const [docs, setDocs] = useState([]);
//   const [activeTab, setActiveTab] = useState('search'); 
//   const [sidebarOpen, setSidebarOpen] = useState(false);

//   // Features State
//   const [searchContext, setSearchContext] = useState('');
//   const [query, setQuery] = useState('');
//   const [searchResult, setSearchResult] = useState('Ready for query.');
//   const [crossResult, setCrossResult] = useState('Select files and click generate.');
//   const [uploadStatus, setUploadStatus] = useState('');
//   const [selectedDocs, setSelectedDocs] = useState(new Set());
//   const [isDragOver, setIsDragOver] = useState(false);

//   // Initial Load
//   useEffect(() => {
//     if (!localStorage.getItem("ranger_token")) navigate('/');
//     fetchDocs();
//   }, []);

//   // --- REFRESH FUNCTION ---
//   const fetchDocs = async () => {
//     try {
//       const res = await api.get('/documents');
//       setDocs(Array.isArray(res.data) ? res.data : []);
//     } catch (e) {
//       console.warn("Backend offline. Switching to Simulation Mode.");
//       setDocs([
//         { filename: "mission_report.pdf", category: "Mission", summary: "Simulation: Mission active." },
//         { filename: "tech_specs.txt", category: "Tech", summary: "Simulation: All systems nominal." },
//       ]);
//     }
//   };

//   const handleLogout = () => {
//     localStorage.removeItem("ranger_token");
//     navigate('/');
//   };

//   const handleSummaryClick = (e, summaryText) => {
//     e.stopPropagation();
//     alert(summaryText || "No summary available for this file.");
//   };

//   // --- NEW: HANDLE PAGE SUMMARY NAVIGATION ---
//   const handlePageSummary = () => {
//     if (selectedDocs.size === 0) return alert("Please select a file first!");
//     if (selectedDocs.size > 1) return alert("For Page-Wise breakdown, please select ONLY ONE file.");
    
//     // Get the single filename from the Set
//     const filename = Array.from(selectedDocs)[0];
    
//     // Navigate to the new page
//     navigate(`/summary?file=${encodeURIComponent(filename)}`);
//   };

//   // --- UPLOAD FUNCTION ---
//   const handleUpload = async (e) => {
//     const file = e.target.files?.[0];
//     if (!file) return;

//     const formData = new FormData();
//     formData.append("file", file);
//     setUploadStatus("Processing...");

//     try {
//       const res = await api.post('/upload', formData, {
//         headers: { "Content-Type": "multipart/form-data" },
//       });
//       setUploadStatus(`Success! Category: ${res.data.category}`);
//       fetchDocs(); 
//     } catch (err) {
//       if (err.response && err.response.status === 500) {
//          setUploadStatus("Error: Backend API limit reached.");
//       } else {
//          setUploadStatus("Error uploading file.");
//       }
//     }
//   };

//   const toggleDocSelection = (filename) => {
//     setSelectedDocs(prev => {
//       const newSet = new Set(prev);
//       if (newSet.has(filename)) newSet.delete(filename);
//       else newSet.add(filename);
//       return newSet;
//     });
//   };

//   const handleDragStart = (e, filename) => e.dataTransfer.setData("filename", filename);
  
//   const handleDrop = (e, panel) => {
//     e.preventDefault();
//     setIsDragOver(false);
//     const filename = e.dataTransfer.getData("filename");
//     if (panel === 'search') setSearchContext(filename);
//     else if (panel === 'cross') {
//       setSelectedDocs(prev => new Set(prev).add(filename));
//       setCrossResult(`[+] Added "${filename}"`);
//     }
//   };

//   const executeSearch = async () => {
//     if (!query) return setSearchResult("Please type a question.");
//     setSearchResult("Searching...");
//     const finalQuery = searchContext ? `Context: ${searchContext}. ${query}` : query;
//     try {
//       const res = await api.get(`/search?query=${encodeURIComponent(finalQuery)}`);
//       setSearchResult(`${res.data.answer}\n\n[Source: ${res.data.citation}]`);
//     } catch (e) { setSearchResult("Error searching."); }
//   };

//   const executeCrossSummary = async () => {
//     if (selectedDocs.size === 0) return alert("Select at least 1 document!");
//     setCrossResult("Synthesizing Report...");
//     try {
//       const res = await api.post('/cross-summary', { filenames: Array.from(selectedDocs) });
//       setCrossResult(res.data.cross_summary);
//     } catch (e) { setCrossResult("Error generating report."); }
//   };

//   return (
//     <div className="dashboard-container">
//       <div className={`overlay ${sidebarOpen ? 'active' : ''}`} onClick={() => setSidebarOpen(false)}></div>

//       {/* SIDEBAR */}
//       <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
//         <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
//           <h2>📂 Intel Library</h2>
//           <button className="mobile-toggle" onClick={() => setSidebarOpen(false)}>✕</button>
//         </div>
        
//         <div className="doc-list">
//           {docs.length === 0 && <div style={{ color: '#666', fontStyle:'italic' }}>No docs found.</div>}
//           {docs.map(doc => (
//             <div 
//               key={doc.filename} 
//               className="doc-item"
//               draggable
//               onDragStart={(e) => handleDragStart(e, doc.filename)}
//             >
//               <input 
//                 type="checkbox" 
//                 checked={selectedDocs.has(doc.filename)}
//                 onChange={() => toggleDocSelection(doc.filename)}
//                 style={{ transform: 'scale(1.2)', marginRight: '10px', cursor:'pointer' }}
//               />
//               <div className="doc-info">
//                 <span className="doc-name">{doc.filename}</span>
//                 <span className="doc-cat">{doc.category}</span>
//               </div>
//               <button 
//                 onClick={(e) => handleSummaryClick(e, doc.summary)}
//                 style={{ background: 'none', border: '1px solid #555', color: '#aaa', borderRadius: '4px', padding:'2px 6px' }}
//                 title="View Summary"
//               >
//                 📄
//               </button>
//             </div>
//           ))}
//         </div>
//         <button className="sidebar-btn btn-refresh" onClick={fetchDocs}>🔄 Refresh List</button>
//         <button className="sidebar-btn btn-logout" onClick={handleLogout}>🛑 Logout</button>
//       </div>

//       {/* MAIN CONTENT */}
//       <div className="main-content">
//         <button className="mobile-toggle" onClick={() => setSidebarOpen(true)}>☰ Menu</button>

//         <h1 style={{ color: 'var(--accent)', marginTop: 0 }}>⚡ Yellow Ranger Console</h1>

//         <div className="upload-zone">
//           <h3>⬆️ Upload New Intel</h3>
//           <input type="file" onChange={handleUpload} style={{ display: 'none' }} id="file-upload" />
//           <button className="action-btn" onClick={() => document.getElementById('file-upload').click()}>
//             Choose File & Upload
//           </button>
//           <p style={{ color: '#aaa', marginTop: '10px' }}>{uploadStatus}</p>
//         </div>

//         <div className="tabs">
//           <div className={`tab ${activeTab === 'search' ? 'active' : ''}`} onClick={() => setActiveTab('search')}>
//             🔍 Semantic Search
//           </div>
//           <div className={`tab ${activeTab === 'cross' ? 'active' : ''}`} onClick={() => setActiveTab('cross')}>
//             🔗 Intelligence Actions
//           </div>
//         </div>

//         {activeTab === 'search' && (
//           <div 
//             className="panel"
//             onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
//             onDragLeave={() => setIsDragOver(false)}
//             onDrop={(e) => handleDrop(e, 'search')}
//             style={isDragOver ? { borderColor: 'var(--accent)', background: '#252525' } : {}}
//           >
//             <h3>Ask the Database</h3>
            
//             <div style={{ marginBottom: '15px' }}>
//               <label style={{ color:'#888', fontSize:'0.9em', display:'block', marginBottom:'5px' }}>
//                 Target Document (Drag file here):
//               </label>
//               <div style={{ display: 'flex', gap: '10px' }}>
//                 <input 
//                   type="text" 
//                   readOnly 
//                   value={searchContext || "Entire Database (Global Search)"}
//                   placeholder="Drag a file here to focus search..." 
//                   style={{ 
//                     width: '100%', padding: '12px', background: '#1a1a1a', 
//                     border: '1px dashed #555', color: searchContext ? 'var(--accent)' : '#666',
//                     cursor: 'default'
//                   }}
//                 />
//                 {searchContext && (
//                   <button 
//                     onClick={() => setSearchContext('')}
//                     style={{ background:'#333', color:'white', padding:'0 15px', borderRadius:'4px' }}
//                   >
//                     ✕ Clear
//                   </button>
//                 )}
//               </div>
//             </div>

//             <div style={{ marginBottom: '15px' }}>
//               <label style={{ color:'#888', fontSize:'0.9em', display:'block', marginBottom:'5px' }}>
//                 Your Question:
//               </label>
//               <input 
//                 type="text" 
//                 placeholder="e.g., Summarize this document, or What is the main topic?" 
//                 value={query}
//                 onChange={(e) => setQuery(e.target.value)}
//                 style={{ width: '100%', padding: '12px', background: '#222', border: '1px solid #444', color: 'white' }}
//                 onKeyDown={(e) => e.key === 'Enter' && executeSearch()}
//               />
//             </div>

//             <button className="action-btn" onClick={executeSearch}>Execute Search</button>
//             <div className="result-box">{searchResult}</div>
//           </div>
//         )}

//         {activeTab === 'cross' && (
//           <div 
//             className="panel"
//             onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
//             onDrop={(e) => handleDrop(e, 'cross')}
//           >
//             <h3>Connect Intelligence</h3>
//             <p>Select documents from the Sidebar list to perform actions.</p>
            
//             {/* BUTTONS CONTAINER */}
//             <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
              
//               {/* BUTTON 1: CROSS SUMMARY */}
//               <button className="action-btn" onClick={executeCrossSummary}>
//                 Generate Connection Report
//               </button>

//               {/* BUTTON 2: PAGE WISE SUMMARY (NEW!) */}
//               <button 
//                 className="action-btn" 
//                 onClick={handlePageSummary}
//                 style={{ background: '#2980b9' }} // Blue color to distinguish it
//               >
//                 📄 View Page-Wise Breakdown
//               </button>
//             </div>

//             <div className="result-box">{crossResult}</div>
//           </div>
//         )}
//       </div>
//     </div>
//   );
// }




// import { useState, useEffect } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { api } from '../services/api';

// export default function Dashboard() {
//   const navigate = useNavigate();
//   const [docs, setDocs] = useState([]);
//   const [activeTab, setActiveTab] = useState('search'); 
//   const [sidebarOpen, setSidebarOpen] = useState(false);

//   // Features State
//   const [searchContext, setSearchContext] = useState('');
//   const [query, setQuery] = useState('');
//   const [searchResult, setSearchResult] = useState('Ready for query.');
//   const [crossResult, setCrossResult] = useState('Select files and click generate.');
//   const [uploadStatus, setUploadStatus] = useState('');
//   const [selectedDocs, setSelectedDocs] = useState(new Set());
//   const [isDragOver, setIsDragOver] = useState(false);

//   // Initial Load
//   useEffect(() => {
//     if (!localStorage.getItem("ranger_token")) navigate('/');
//     fetchDocs();
//   }, []);

//   // --- REFRESH FUNCTION ---
//   const fetchDocs = async () => {
//     try {
//       const res = await api.get('/documents');
//       setDocs(Array.isArray(res.data) ? res.data : []);
//     } catch (e) {
//       console.warn("Backend offline. Switching to Simulation Mode.");
//       setDocs([
//         { filename: "mission_report.pdf", category: "Mission", summary: "Simulation: Mission active." },
//         { filename: "tech_specs.txt", category: "Tech", summary: "Simulation: All systems nominal." },
//       ]);
//     }
//   };

//   const handleLogout = () => {
//     localStorage.removeItem("ranger_token");
//     navigate('/');
//   };

//   const handleSummaryClick = (e, summaryText) => {
//     e.stopPropagation();
//     alert(summaryText || "No summary available for this file.");
//   };

//   // --- UPLOAD FUNCTION ---
//   const handleUpload = async (e) => {
//     const file = e.target.files?.[0];
//     if (!file) return;

//     const formData = new FormData();
//     formData.append("file", file);
//     setUploadStatus("Processing...");

//     try {
//       const res = await api.post('/upload', formData, {
//         headers: { "Content-Type": "multipart/form-data" },
//       });
//       setUploadStatus(`Success! Category: ${res.data.category}`);
//       fetchDocs(); 
//     } catch (err) {
//       if (err.response && err.response.status === 500) {
//          setUploadStatus("Error: Backend API limit reached.");
//       } else {
//          setUploadStatus("Error uploading file.");
//       }
//     }
//   };

//   const toggleDocSelection = (filename) => {
//     setSelectedDocs(prev => {
//       const newSet = new Set(prev);
//       if (newSet.has(filename)) newSet.delete(filename);
//       else newSet.add(filename);
//       return newSet;
//     });
//   };

//   const handleDragStart = (e, filename) => e.dataTransfer.setData("filename", filename);
  
//   const handleDrop = (e, panel) => {
//     e.preventDefault();
//     setIsDragOver(false);
//     const filename = e.dataTransfer.getData("filename");
//     if (panel === 'search') setSearchContext(filename);
//     else if (panel === 'cross') {
//       setSelectedDocs(prev => new Set(prev).add(filename));
//       setCrossResult(`[+] Added "${filename}"`);
//     }
//   };

//   const executeSearch = async () => {
//     if (!query) return setSearchResult("Please type a question.");
//     setSearchResult("Searching...");
//     const finalQuery = searchContext ? `Context: ${searchContext}. ${query}` : query;
//     try {
//       const res = await api.get(`/search?query=${encodeURIComponent(finalQuery)}`);
//       setSearchResult(`${res.data.answer}\n\n[Source: ${res.data.citation}]`);
//     } catch (e) { setSearchResult("Error searching."); }
//   };

//   const executeCrossSummary = async () => {
//     if (selectedDocs.size === 0) return alert("Select at least 1 document!");
//     setCrossResult("Synthesizing Report...");
//     try {
//       const res = await api.post('/cross-summary', { filenames: Array.from(selectedDocs) });
//       setCrossResult(res.data.cross_summary);
//     } catch (e) { setCrossResult("Error generating report."); }
//   };

//   return (
//     <div className="dashboard-container">
//       <div className={`overlay ${sidebarOpen ? 'active' : ''}`} onClick={() => setSidebarOpen(false)}></div>

//       {/* SIDEBAR */}
//       <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
//         <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
//           <h2>📂 Intel Library</h2>
//           <button className="mobile-toggle" onClick={() => setSidebarOpen(false)}>✕</button>
//         </div>
        
//         <div className="doc-list">
//           {docs.length === 0 && <div style={{ color: '#666', fontStyle:'italic' }}>No docs found.</div>}
//           {docs.map(doc => (
//             <div 
//               key={doc.filename} 
//               className="doc-item"
//               draggable
//               onDragStart={(e) => handleDragStart(e, doc.filename)}
//             >
//               <input 
//                 type="checkbox" 
//                 checked={selectedDocs.has(doc.filename)}
//                 onChange={() => toggleDocSelection(doc.filename)}
//                 style={{ transform: 'scale(1.2)', marginRight: '10px', cursor:'pointer' }}
//               />
//               <div className="doc-info">
//                 <span className="doc-name">{doc.filename}</span>
//                 <span className="doc-cat">{doc.category}</span>
//               </div>
//               <button 
//                 onClick={(e) => handleSummaryClick(e, doc.summary)}
//                 style={{ background: 'none', border: '1px solid #555', color: '#aaa', borderRadius: '4px', padding:'2px 6px' }}
//                 title="View Summary"
//               >
//                 📄
//               </button>
//             </div>
//           ))}
//         </div>
//         <button className="sidebar-btn btn-refresh" onClick={fetchDocs}>🔄 Refresh List</button>
//         <button className="sidebar-btn btn-logout" onClick={handleLogout}>🛑 Logout</button>
//       </div>

//       {/* MAIN CONTENT */}
//       <div className="main-content">
//         <button className="mobile-toggle" onClick={() => setSidebarOpen(true)}>☰ Menu</button>

//         <h1 style={{ color: 'var(--accent)', marginTop: 0 }}>⚡ Yellow Ranger Console</h1>

//         <div className="upload-zone">
//           <h3>⬆️ Upload New Intel</h3>
//           <input type="file" onChange={handleUpload} style={{ display: 'none' }} id="file-upload" />
//           <button className="action-btn" onClick={() => document.getElementById('file-upload').click()}>
//             Choose File & Upload
//           </button>
//           <p style={{ color: '#aaa', marginTop: '10px' }}>{uploadStatus}</p>
//         </div>

//         <div className="tabs">
//           <div className={`tab ${activeTab === 'search' ? 'active' : ''}`} onClick={() => setActiveTab('search')}>
//             🔍 Semantic Search
//           </div>
//           <div className={`tab ${activeTab === 'cross' ? 'active' : ''}`} onClick={() => setActiveTab('cross')}>
//             🔗 Cross-Summary
//           </div>
//         </div>

//         {activeTab === 'search' && (
//           <div 
//             className="panel"
//             onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
//             onDragLeave={() => setIsDragOver(false)}
//             onDrop={(e) => handleDrop(e, 'search')}
//             style={isDragOver ? { borderColor: 'var(--accent)', background: '#252525' } : {}}
//           >
//             <h3>Ask the Database</h3>
            
//             <div style={{ marginBottom: '15px' }}>
//               <label style={{ color:'#888', fontSize:'0.9em', display:'block', marginBottom:'5px' }}>
//                 Target Document (Drag file here):
//               </label>
//               <div style={{ display: 'flex', gap: '10px' }}>
//                 <input 
//                   type="text" 
//                   readOnly 
//                   value={searchContext || "Entire Database (Global Search)"}
//                   placeholder="Drag a file here to focus search..." 
//                   style={{ 
//                     width: '100%', padding: '12px', background: '#1a1a1a', 
//                     border: '1px dashed #555', color: searchContext ? 'var(--accent)' : '#666',
//                     cursor: 'default'
//                   }}
//                 />
//                 {searchContext && (
//                   <button 
//                     onClick={() => setSearchContext('')}
//                     style={{ background:'#333', color:'white', padding:'0 15px', borderRadius:'4px' }}
//                   >
//                     ✕ Clear
//                   </button>
//                 )}
//               </div>
//             </div>

//             <div style={{ marginBottom: '15px' }}>
//               <label style={{ color:'#888', fontSize:'0.9em', display:'block', marginBottom:'5px' }}>
//                 Your Question:
//               </label>
//               <input 
//                 type="text" 
//                 placeholder="e.g., Summarize this document, or What is the main topic?" 
//                 value={query}
//                 onChange={(e) => setQuery(e.target.value)}
//                 style={{ width: '100%', padding: '12px', background: '#222', border: '1px solid #444', color: 'white' }}
//                 onKeyDown={(e) => e.key === 'Enter' && executeSearch()}
//               />
//             </div>

//             <button className="action-btn" onClick={executeSearch}>Execute Search</button>
//             <div className="result-box">{searchResult}</div>
//           </div>
//         )}

//         {activeTab === 'cross' && (
//           <div 
//             className="panel"
//             onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
//             onDrop={(e) => handleDrop(e, 'cross')}
//           >
//             <h3>Connect Intelligence</h3>
//             <p>Select documents from the Sidebar list.</p>
//             <button className="action-btn" onClick={executeCrossSummary}>Generate Report</button>
//             <div className="result-box">{crossResult}</div>
//           </div>
//         )}
//       </div>
//     </div>
//   );
// }
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import PageSummary from './pages/PageSummary'; // <--- 1. IMPORT THE NEW PAGE

function App() {
  // Simple check to see if user is logged in
  const isAuthenticated = !!localStorage.getItem("ranger_token");

  return (
    <BrowserRouter>
      <Routes>
        {/* Login Page */}
        <Route path="/" element={<Login />} />
        
        {/* Dashboard (Protected) */}
        <Route 
          path="/dashboard" 
          element={isAuthenticated ? <Dashboard /> : <Navigate to="/" />} 
        />

        {/* --- 2. ADD THIS NEW ROUTE --- */}
        <Route 
          path="/summary" 
          element={isAuthenticated ? <PageSummary /> : <Navigate to="/" />} 
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;


// import { BrowserRouter, Routes, Route } from 'react-router-dom';
// import Login from './pages/Login';
// import Dashboard from './pages/Dashboard';

// function App() {
//   // No useEffect needed here anymore! 
//   // index.html handles the initial theme load perfectly.

//   return (
//     <BrowserRouter>
//       <Routes>
//         <Route path="/" element={<Login />} />
//         <Route path="/dashboard" element={<Dashboard />} />
//       </Routes>
//     </BrowserRouter>
//   );
// }

// export default App;

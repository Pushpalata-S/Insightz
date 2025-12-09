import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  
  // STRICT FIELDS
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [msg, setMsg] = useState('');
  
  const navigate = useNavigate();

  const handleAuth = async () => {
    setMsg(""); // Clear errors

    // 1. Validation
    if (!username || !password) {
      setMsg("Username and Password are required");
      return;
    }
    if (!isLogin && !email) {
      setMsg("Email is required for registration");
      return;
    }

    try {
      const endpoint = isLogin ? '/login' : '/signup';
      
      // 2. Exact Payload Construction
      const payload = isLogin 
        ? { username: username, password: password }
        : { username: username, email: email, password: password };

      console.log("Sending Payload:", payload); // Check console (F12) if it fails

      const res = await api.post(endpoint, payload);
      
      if (isLogin) {
        // Login Success
        localStorage.setItem("ranger_token", res.data.token);
        localStorage.setItem("ranger_user", res.data.username);
        navigate('/dashboard');
      } else {
        // Signup Success
        setMsg("Registration Successful! Please Login.");
        setIsLogin(true);
        setPassword('');
        setEmail('');
      }
    } catch (err) {
      console.error("Login Error:", err);
      // Show the specific error from the backend if available
      setMsg(err.response?.data?.detail || "Connection Failed. Check Python Console.");
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    setMsg("");
    setUsername("");
    setEmail("");
    setPassword("");
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>
          <span style={{ fontSize: '1.2em', marginRight: '10px' }}>⚡</span> 
          RANGER {isLogin ? "LOGIN" : "REGISTER"}
        </h1>
        
        {/* FIELD 1: USERNAME (Always Visible) */}
        <input 
          type="text" 
          placeholder="Username" 
          value={username} 
          onChange={(e) => setUsername(e.target.value)} 
        />

        {/* FIELD 2: EMAIL (Only for Register) */}
        {!isLogin && (
          <input 
            type="email" 
            placeholder="Email Address" 
            value={email} 
            onChange={(e) => setEmail(e.target.value)} 
          />
        )}

        {/* FIELD 3: PASSWORD (Always Visible) */}
        <input 
          type="password" 
          placeholder="Password" 
          value={password} 
          onChange={(e) => setPassword(e.target.value)} 
          onKeyDown={(e) => e.key === 'Enter' && handleAuth()} 
        />
        
        <button onClick={handleAuth}>
          {isLogin ? "Access Console" : "Create Account"}
        </button>

        <div className="toggle-link" onClick={toggleMode}>
          {isLogin ? "Need an account? Register" : "Have an account? Login"}
        </div>

        <div className="error-msg">{msg}</div>
      </div>
    </div>
  );
}
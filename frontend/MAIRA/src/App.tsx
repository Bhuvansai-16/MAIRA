import { Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { ThreadProvider } from "./context/ThreadContext";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { Toaster } from "sonner";

function ChatLayout() {
  return (
    <div className="flex h-screen w-full bg-black text-foreground overflow-hidden">
      <Sidebar />
      <ChatArea />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Toaster
        position="top-center"
        toastOptions={{
          style: {
            background: '#1a1a1a',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#fff',
            fontSize: '14px',
          },
        }}
        richColors
        closeButton
      />
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        
        {/* Protected chat routes - single route with optional threadId to prevent remounting */}
        <Route
          path="/chat/:threadId?"
          element={
            <ProtectedRoute>
              <ThreadProvider>
                <ChatLayout />
              </ThreadProvider>
            </ProtectedRoute>
          }
        />
        
        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;



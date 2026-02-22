import { Routes, Route, Navigate } from "react-router-dom";
import SmoothScroll from "./components/SmoothScroll";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { ThreadProvider } from "./context/ThreadContext";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { PaperWriter } from "./pages/PaperWriter";
import { Toaster } from "sonner";

function ChatLayout() {
  return (
    <div className="dark flex h-screen w-full bg-black text-foreground overflow-hidden">
      <Sidebar />
      <ChatArea />
    </div>
  );
}

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
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
          <Route path="/paper-writer" element={
            <ProtectedRoute>
              <div className="dark w-full h-screen">
                <PaperWriter />
              </div>
            </ProtectedRoute>
          } />

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
        <SmoothScroll />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;



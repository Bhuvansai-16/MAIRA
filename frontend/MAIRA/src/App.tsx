import { Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { ThreadProvider } from "./context/ThreadContext";

function AppLayout() {
  return (
    <div className="flex h-screen w-full bg-black text-foreground">
      <Sidebar />
      <ChatArea />
    </div>
  );
}

function App() {
  return (
    <ThreadProvider>
      <Routes>
        {/* Chat route with optional thread ID */}
        <Route path="/chat" element={<AppLayout />} />
        <Route path="/chat/:threadId" element={<AppLayout />} />
        {/* Redirect root to /chat */}
        <Route path="/" element={<Navigate to="/chat" replace />} />
        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </ThreadProvider>
  );
}

export default App;



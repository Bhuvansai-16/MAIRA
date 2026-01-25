import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { ThreadProvider } from "./context/ThreadContext";

function App() {
  return (
    <ThreadProvider>
      <div className="flex h-screen w-full bg-black text-foreground">
        <Sidebar />
        <ChatArea />
      </div>
    </ThreadProvider>
  );
}

export default App;



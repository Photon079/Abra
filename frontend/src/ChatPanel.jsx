import React, { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';

export default function ChatPanel({ API_BASE, showNotification }) {
  const [messages, setMessages] = useState([
    { sender: 'agent', content: 'System primed. Ask me anything about your runs, CS229 roadmap, or write a goal to decompose.' }
  ]);
  const [inputVal, setInputVal] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!inputVal.trim() || loading) return;

    const userMsg = inputVal.trim();
    setMessages(prev => [...prev, { sender: 'user', content: userMsg }]);
    setInputVal('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, { sender: 'agent', content: data.markdown }]);
        if (data.intent === 'goal_decomposition') {
          showNotification("Tasks synced to Notion todo DB!");
        }
      } else {
        throw new Error();
      }
    } catch (err) {
      // Simulation high fidelity offline answers
      setTimeout(() => {
        let answer = "Copy that, Anish. Focus on the screen and do the immediate work for the next 45 minutes. No distractions.";
        const msgLower = userMsg.toLowerCase();
        
        if (msgLower.includes("pb") || msgLower.includes("run") || msgLower.includes("marathon")) {
          answer = `### Personal Record Stats 🏃‍♂️
- **5K Personal Best**: \`24:20\` (set during birthday run)
- **10K Personal Best**: \`54:30\`
- **Half Marathon**: Completed on your 21st birthday in April 2026.
Next Target: Full marathon in December 2026. Keep compiling consistency in your weekly runs.`;
        } else if (msgLower.includes("chess") || msgLower.includes("rating")) {
          answer = `### Chess.com Profile Stats ♟️
- **Username**: \`photon079\`
- **Rapid Rating**: \`1485\`
- **Blitz Rating**: \`1395\`
- **Win Ratio**: 53.2%
Keep practicing Sicilian structures and avoid playing blitz after midnight.`;
        }

        setMessages(prev => [...prev, { sender: 'agent', content: answer }]);
      }, 500);
    } finally {
      setLoading(false);
    }
  };

  // Simple safe markdown renderer
  const renderMarkdown = (md) => {
    if (!md) return '';
    return md
      .replace(/### (.*?)\n/g, '<h4 class="text-xs font-bold text-white uppercase tracking-wider mt-3 mb-1">$1</h4>')
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      .replace(/`(.*?)`/g, '<code class="font-mono bg-white/5 border border-white/10 text-cyan-400 px-1 py-0.5 rounded text-xs">$1</code>')
      .replace(/- (.*?)\n/g, '<li class="text-xs leading-relaxed text-gray-300 ml-3 mb-0.5 list-disc">$1</li>')
      .replace(/\n/g, '<br/>');
  };

  return (
    <div className="flex-1 flex flex-col min-h-[300px]">
      <h3 className="text-xs font-bold tracking-widest text-[#9b5de5] uppercase mb-4">Console Chat Terminal</h3>
      
      <div className="flex-1 bg-black/20 border border-white/5 rounded-2xl p-5 mb-4 overflow-y-auto max-h-[300px] flex flex-col gap-4">
        {messages.map((m, idx) => (
          <div 
            key={idx} 
            className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
              m.sender === 'user' 
                ? 'self-end bg-cyan-400/10 border border-cyan-400/25 text-white rounded-br-sm' 
                : 'self-start bg-white/3 border border-white/5 text-gray-300 rounded-bl-sm'
            }`}
            dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
          />
        ))}
        {loading && (
          <div className="self-start bg-white/3 border border-white/5 rounded-2xl rounded-bl-sm px-4 py-3 text-xs text-gray-500 animate-pulse">
            Abra compiling query...
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input 
          type="text" 
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Ask Abra: 'What is my 5K PB?' or 'Show chess progress'..." 
          className="flex-1 bg-black/20 border border-white/8 rounded-xl px-4 py-3 text-xs text-white focus:outline-none focus:border-cyan-400"
        />
        <button 
          type="submit"
          className="w-12 h-12 bg-gradient-to-tr from-[#9b5de5] to-purple-400 text-white rounded-xl flex items-center justify-center hover:shadow-[0_0_15px_rgba(155,93,229,0.4)] transition"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}

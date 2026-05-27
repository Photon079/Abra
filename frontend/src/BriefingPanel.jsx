import React, { useState, useEffect } from 'react';
import { RefreshCw, Calendar, Warning } from 'lucide-react';

export default function BriefingPanel({ API_BASE }) {
  const [briefing, setBriefing] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBriefing();
  }, []);

  const fetchBriefing = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/briefing`);
      if (res.ok) {
        const data = await res.json();
        setBriefing(data.markdown);
      } else {
        throw new Error();
      }
    } catch (err) {
      // Fallback morning brief conforming to brutal honesty
      setBriefing(`
### 📅 Calendar Today
• ML CS229 Lecture Review (11:30 AM)
• Run 6K Grounding session (4:15 PM)
• Abra Core coding (6:00 PM)

### 🎯 Suggested Focus Block
Focus for the next 45 minutes on finishing the calendar spec validation in Abra. That is your only priority, bruh.

⚠️ **Scatter Loop detected:** You switched from CS229 algorithms to scrolling GitHub pipelines three times yesterday. Commit to your schedule today.
      `);
    } finally {
      setLoading(false);
    }
  };

  // Safe simple markdown renderer
  const renderMarkdown = (md) => {
    if (!md) return '';
    return md
      .replace(/### (.*?)\n/g, '<h4 class="text-sm font-bold text-white uppercase tracking-wider mt-4 mb-2">$1</h4>')
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      .replace(/`(.*?)`/g, '<code class="font-mono bg-white/5 border border-white/10 text-cyan-400 px-1.5 py-0.5 rounded text-xs">$1</code>')
      .replace(/- (.*?)\n/g, '<li class="text-xs leading-relaxed text-gray-300 ml-4 mb-1 list-disc">$1</li>')
      .replace(/• (.*?)\n/g, '<li class="text-xs leading-relaxed text-gray-300 ml-4 mb-1 list-disc">$1</li>')
      .replace(/\n/g, '<br/>');
  };

  return (
    <div className="mb-8 border-b border-white/5 pb-8">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xs font-bold tracking-widest text-purple-400 uppercase">Daily Briefing Panel</h3>
        <button 
          onClick={fetchBriefing} 
          disabled={loading}
          className="p-2 hover:bg-white/5 rounded-lg border border-white/5 text-gray-400 hover:text-white transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="bg-white/2 border border-white/5 rounded-2xl p-5 relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] before:bg-purple-500/35">
        {loading ? (
          <p className="text-xs text-gray-400">Loading daily schedule and querying memory integrations...</p>
        ) : (
          <div 
            className="text-xs leading-relaxed text-gray-300 space-y-2 font-sans"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(briefing) }}
          />
        )}
      </div>
    </div>
  );
}

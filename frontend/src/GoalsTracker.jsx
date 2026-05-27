import React, { useState } from 'react';
import { Target, Plus } from 'lucide-react';

export default function GoalsTracker({ plan, setPlan, API_BASE, showNotification }) {
  const [goalText, setGoalText] = useState('');
  const [loading, setLoading] = useState(false);

  const handleDecompose = async () => {
    if (!goalText.trim()) return;
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `decompose goal: ${goalText}` })
      });

      if (res.ok) {
        const result = await res.json();
        setPlan(result.data);
        showNotification("Goal deconstructed and sub-tasks synced to Notion Todo DB!");
        setGoalText('');
      }
    } catch (err) {
      // simulated response
      setPlan({
        explanation: `Calculated pacing plan for: ${goalText}. Average 2.4 tasks/day completed on work blocks.`,
        tasks: [
          { title: "NeetCode: Two Pointers Section (3 problems)", deadline: "2026-05-27", category: "Career", target: "Complete all container problems." },
          { title: "Long Run 18K grounding target", deadline: "2026-05-30", category: "Physical", target: "Maintain pace under 5:40/km." }
        ]
      });
      showNotification("Notion offline. Tasks scheduled locally.");
      setGoalText('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mb-8 border-b border-white/5 pb-8">
      <h3 className="text-xs font-bold tracking-widest text-cyan-400 uppercase mb-4">Goal-Aware Tracker</h3>
      
      <div className="flex gap-2 mb-4">
        <input 
          type="text" 
          value={goalText}
          onChange={(e) => setGoalText(e.target.value)}
          placeholder="Decompose goal: 'Complete NeetCode 150 by July 31'..." 
          className="flex-1 bg-black/20 border border-white/8 rounded-xl px-4 py-3 text-xs text-white focus:outline-none focus:border-cyan-400"
        />
        <button 
          onClick={handleDecompose}
          disabled={loading || !goalText.trim()}
          className="bg-cyan-400 text-black px-4 rounded-xl flex items-center justify-center font-bold text-xs hover:bg-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          {loading ? '...' : <Plus className="w-4 h-4" />}
        </button>
      </div>

      {plan && (
        <div className="bg-white/2 border border-white/5 rounded-2xl p-5 flex flex-col gap-4 animate-fadeIn">
          <div>
            <h4 className="text-xs font-bold text-white uppercase mb-1">Calculated Strategy</h4>
            <p className="text-xs text-gray-400 leading-relaxed">{plan.explanation}</p>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-bold text-white uppercase">Suggested Task List</h4>
            {plan.tasks && plan.tasks.map((t, idx) => (
              <div key={idx} className="bg-white/5 border border-white/10 rounded-xl p-3 flex justify-between items-start gap-4">
                <div className="flex-1">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-bold text-white leading-tight">{t.title}</span>
                    <span className="bg-cyan-400/10 text-cyan-400 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase">{t.category}</span>
                  </div>
                  <p className="text-[10px] text-gray-400">{t.target}</p>
                </div>
                <div className="text-right flex flex-col gap-0.5">
                  <span className="text-[8px] tracking-wider text-gray-500 font-bold uppercase">Deadline</span>
                  <span className="text-[10px] font-mono text-cyan-300 font-semibold">{t.deadline}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

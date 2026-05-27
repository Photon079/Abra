import React from 'react';

export default function DiaryCard({ log }) {
  if (!log) return null;

  return (
    <div className="mt-6 border border-cyan-500/20 bg-cyan-500/5 rounded-2xl p-5 flex flex-col gap-4 animate-fadeIn">
      <div className="flex justify-between items-center">
        <h4 className="text-xs font-bold tracking-widest text-cyan-400 uppercase">Latest Committed Entry</h4>
        <span className="bg-cyan-400/10 text-cyan-400 px-3 py-1 rounded-full text-[10px] font-bold uppercase">{log.mood}</span>
      </div>
      
      <div>
        <h5 className="text-xs font-semibold text-white uppercase tracking-wider mb-1">Activities</h5>
        <div className="flex flex-wrap gap-2">
          {log.activities && log.activities.map((act, i) => (
            <span key={i} className="bg-white/5 border border-white/10 text-gray-300 px-2.5 py-0.5 rounded-full text-xs font-medium">{act}</span>
          ))}
        </div>
      </div>

      <div>
        <h5 className="text-xs font-semibold text-white uppercase tracking-wider mb-1">Summary</h5>
        <p className="text-xs leading-relaxed text-gray-300">{log.summary}</p>
      </div>

      {log.decisions && (
        <div>
          <h5 className="text-xs font-semibold text-white uppercase tracking-wider mb-1">Key Decisions</h5>
          <p className="text-xs leading-relaxed text-gray-300">{log.decisions}</p>
        </div>
      )}

      <div>
        <h5 className="text-xs font-semibold text-white uppercase tracking-wider mb-1">Suggested Focus for Tomorrow</h5>
        <p className="text-xs leading-relaxed text-cyan-300 font-semibold">• {log.tomorrow_focus}</p>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { Mic, RefreshCw, Send, ShieldAlert, Award, FileText, CheckCircle, Database } from 'lucide-react';
import BriefingPanel from './BriefingPanel';
import DiaryCard from './DiaryCard';
import GoalsTracker from './GoalsTracker';
import ChatPanel from './ChatPanel';

export default function App() {
  const [status, setStatus] = useState({ notion: 'local_fallback', coral_cli: 'simulated', llm_provider: 'gemini', llm_configured: false });
  const [transcription, setTranscription] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recognition, setRecognition] = useState(null);
  const [diaryEntry, setDiaryEntry] = useState(null);
  const [goalsPlan, setGoalsPlan] = useState(null);
  const [toast, setToast] = useState('');

  const API_BASE = 'http://127.0.0.1:8000/api';

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.warn("API Server offline. Utilizing high-fidelity simulation model.");
    }
  };

  const showNotification = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 4000);
  };

  const handleStartRecording = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Web Speech API not supported in this browser. Please type in chat.");
      return;
    }

    const recObj = new SpeechRecognition();
    recObj.continuous = true;
    recObj.interimResults = true;
    recObj.lang = 'en-IN';

    recObj.onstart = () => {
      setIsRecording(true);
      setTranscription('');
    };

    recObj.onresult = (event) => {
      let current = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        current += event.results[i][0].transcript + ' ';
      }
      setTranscription(current);
    };

    recObj.onerror = (event) => {
      setIsRecording(false);
      showNotification("Voice error: " + event.error);
    };

    recObj.onend = () => {
      setIsRecording(false);
    };

    recObj.start();
    setRecognition(recObj);
  };

  const handleStopRecording = () => {
    if (recognition) {
      recognition.stop();
    }
    setIsRecording(false);
  };

  const handleClear = () => {
    handleStopRecording();
    setTranscription('');
  };

  const handleCommitDiary = async () => {
    if (!transcription.trim()) return;

    try {
      const res = await fetch(`${API_BASE}/voice-diary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcription })
      });

      if (res.ok) {
        const result = await res.json();
        setDiaryEntry(result.data);
        showNotification("Structured diary log committed successfully to Notion!");
      }
    } catch (err) {
      // Offline fallback simulation
      setDiaryEntry({
        summary: transcription,
        mood: 'Focused',
        activities: ['Coding', 'Running'],
        decisions: 'Resolved to deploy local simulation layers.',
        tomorrow_focus: 'Verify server connection.'
      });
      showNotification("Notion offline. Simulated diary logged locally.");
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0c10] text-[#c5c6c7] font-sans antialiased">
      {/* Header bar */}
      <header className="px-10 py-6 flex justify-between items-center border-b border-cyan-500/10 backdrop-blur sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 height-8 rounded-full bg-gradient-to-tr from-cyan-400 to-purple-500 shadow-[0_0_15px_rgba(102,252,241,0.4)] animate-pulse" />
          <h1 className="text-2xl font-extrabold tracking-wider text-white uppercase font-display">
            Abra <span className="bg-gradient-to-r from-cyan-400 to-teal-300 bg-clip-text text-transparent">Life OS</span>
          </h1>
        </div>
        <div className="flex gap-4">
          <div className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-xs font-semibold flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${status.notion === 'connected' ? 'bg-cyan-400 shadow-[0_0_8px_rgba(102,252,241,0.5)]' : 'bg-purple-500'}`} />
            Notion: {status.notion === 'connected' ? 'Connected' : 'Local Fallback'}
          </div>
          <div className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-xs font-semibold flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${status.coral_cli === 'connected' ? 'bg-cyan-400 shadow-[0_0_8px_rgba(102,252,241,0.5)]' : 'bg-amber-500'}`} />
            Coral: {status.coral_cli === 'connected' ? 'CLI Active' : 'Simulated'}
          </div>
          <div className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-xs font-semibold flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${status.llm_configured ? 'bg-cyan-400 shadow-[0_0_8px_rgba(102,252,241,0.5)]' : 'bg-amber-500'}`} />
            Provider: {status.llm_provider.toUpperCase()}
          </div>
        </div>
      </header>

      {/* Workspace panel structure */}
      <main className="max-w-[1400px] mx-auto p-10 grid grid-cols-1 lg:grid-cols-2 gap-10">
        
        {/* Voice Logger Module */}
        <section className="bg-[#1f2833]/40 border border-cyan-500/15 rounded-3xl backdrop-blur-md shadow-2xl p-8 flex flex-col relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-cyan-400 before:to-purple-500">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-3">
            <Mic className="text-cyan-400" /> Voice Portal Entry
          </h2>

          <div className="flex flex-col items-center justify-center flex-1 gap-8 py-10">
            <div 
              className={`relative cursor-pointer w-32 h-32 flex items-center justify-center rounded-full border-2 ${isRecording ? 'border-pink-500 bg-pink-500/10 shadow-[0_0_30px_rgba(255,0,127,0.3)] animate-pulse' : 'border-cyan-400 bg-cyan-400/5 hover:scale-105'} transition-all duration-300 z-10`}
              onClick={isRecording ? handleStopRecording : handleStartRecording}
            >
              <span className="text-4xl">{isRecording ? '🛑' : '🎤'}</span>
            </div>

            <p className={`text-sm text-center ${isRecording ? 'text-pink-500 font-semibold animate-bounce' : 'text-gray-400'}`}>
              {isRecording ? 'Recording voice dump... speak naturally, bruh.' : 'Click mic to log your daily dump.'}
            </p>

            <textarea 
              className="w-full bg-black/25 border border-white/5 rounded-2xl p-5 min-h-[100px] max-h-[150px] overflow-y-auto font-mono text-xs text-gray-300 leading-relaxed resize-none focus:outline-none focus:border-cyan-400/50"
              placeholder="Captured transcript will manifest here in real-time... (or type your dump manually)"
              value={transcription}
              onChange={(e) => setTranscription(e.target.value)}
            />

            <div className="flex gap-4 w-full">
              <button onClick={handleClear} className="flex-1 py-3.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-sm font-semibold uppercase tracking-wider">Clear</button>
              <button 
                onClick={handleCommitDiary} 
                disabled={!transcription.trim()}
                className="flex-1 py-3.5 rounded-xl bg-gradient-to-r from-cyan-400 to-teal-300 text-[#0b0c10] font-bold text-sm hover:shadow-[0_0_20px_rgba(102,252,241,0.4)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed uppercase tracking-wider"
              >
                Commit to Notion
              </button>
            </div>
          </div>
          
          {diaryEntry && <DiaryCard log={diaryEntry} />}
        </section>

        {/* Console Dashboard Module */}
        <section className="bg-[#1f2833]/40 border border-cyan-500/15 rounded-3xl backdrop-blur-md shadow-2xl p-8 flex flex-col relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-purple-500 before:to-cyan-400">
          <BriefingPanel API_BASE={API_BASE} />
          
          <GoalsTracker plan={goalsPlan} setPlan={setGoalsPlan} API_BASE={API_BASE} showNotification={showNotification} />
          
          <ChatPanel API_BASE={API_BASE} showNotification={showNotification} />
        </section>
      </main>

      {/* Notifications */}
      {toast && (
        <div className="fixed bottom-8 right-8 z-50 bg-[#0b0c10] border border-cyan-400 shadow-[0_0_20px_rgba(102,252,241,0.2)] rounded-xl px-5 py-4 text-xs font-semibold text-white flex items-center gap-3 animate-bounce">
          <div className="w-5 h-5 rounded bg-white text-black flex items-center justify-center font-bold">N</div>
          {toast}
        </div>
      )}
    </div>
  );
}

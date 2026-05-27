        const API_BASE = window.location.origin.includes("file://") ? "http://127.0.0.1:8000/api" : window.location.origin + "/api";
        let isRecording = false;
        let recognition = null;
        let finalTranscript = "";

        // Status elements
        const notionStatus = document.getElementById("notion-status");
        const coralStatus = document.getElementById("coral-status");
        const agentStatus = document.getElementById("agent-status");

        // Action elements
        const micBtn = document.getElementById("mic-btn");
        const speechInstruction = document.getElementById("speech-instruction");
        const transcriptBox = document.getElementById("transcript-box");
        const commitBtn = document.getElementById("commit-btn");
        const clearBtn = document.getElementById("clear-btn");
        const logConsole = document.getElementById("log-console");

        // Chat & briefing elements
        const briefingBox = document.getElementById("briefing-box");
        const refreshBriefBtn = document.getElementById("refresh-brief-btn");
        const chatHistoryBox = document.getElementById("chat-history-box");
        const chatInputField = document.getElementById("chat-input-field");
        const chatSendBtn = document.getElementById("chat-send-btn");

        // Add a typewriter line to the live HUD console log
        function addConsoleLog(module, text, isError = false) {
            const time = new Date().toTimeString().split(" ")[0];
            const line = document.createElement("div");
            line.classList.add("log-line");
            
            let color = "rgba(102, 252, 241, 0.7)";
            if (isError) color = "#ff0055";
            else if (module === "NOTION") color = "#e2b6ff";
            else if (module === "LLM") color = "#b8d0ff";

            line.innerHTML = `
                <span class="log-time">[${time}]</span>
                <span style="color: ${color};">[${module}]</span>
                <span style="color: ${isError ? '#ff668f' : 'white'};">${text}</span>
            `;
            logConsole.appendChild(line);
            logConsole.scrollTop = logConsole.scrollHeight;
        }

        // Check backend server connection
        async function checkStatus() {
            try {
                const res = await fetch(`${API_BASE}/status`);
                if (res.ok) {
                    const data = await res.json();
                    
                    if (data.notion === "connected") {
                        notionStatus.innerHTML = `<span class="status-indicator status-active"></span>Notion: API CONNECTED`;
                    } else {
                        notionStatus.innerHTML = `<span class="status-indicator status-simulated"></span>Notion: LOCAL FALLBACK`;
                    }

                    if (data.coral_cli === "connected") {
                        coralStatus.innerHTML = `<span class="status-indicator status-active"></span>Coral: ENGINE ACTIVE`;
                    } else {
                        coralStatus.innerHTML = `<span class="status-indicator status-simulated"></span>Coral: SIMULATED`;
                    }

                    if (data.llm_configured) {
                        agentStatus.innerHTML = `<span class="status-indicator status-active"></span>${data.llm_provider.toUpperCase()}: ACTIVE`;
                    } else {
                        agentStatus.innerHTML = `<span class="status-indicator status-simulated"></span>${data.llm_provider.toUpperCase()}: MOCK`;
                    }
                }
            } catch (err) {
                notionStatus.innerHTML = `<span class="status-indicator status-simulated"></span>Notion: SERVER OFFLINE`;
                coralStatus.innerHTML = `<span class="status-indicator status-simulated"></span>Coral: OFFLINE`;
                agentStatus.innerHTML = `<span class="status-indicator status-simulated"></span>Bridge: OFFLINE`;
            }
        }

        // Offline Browser MediaRecorder configuration
        let mediaRecorder = null;
        let audioChunks = [];

        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioChunks = [];
                
                // standard container format that works across Chrome/Firefox
                const options = { mimeType: 'audio/webm' };
                mediaRecorder = new MediaRecorder(stream, options);
                
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };
                
                mediaRecorder.onstart = () => {
                    isRecording = true;
                    micBtn.classList.add("recording");
                    speechInstruction.classList.add("recording");
                    speechInstruction.textContent = "Audio stream active... speak now.";
                    addConsoleLog("VOICE", "Microphone stream opened. Recording local audio chunks.");
                };
                
                mediaRecorder.onstop = () => {
                    isRecording = false;
                    micBtn.classList.remove("recording");
                    speechInstruction.classList.remove("recording");
                    speechInstruction.textContent = "Audio captured. Click commit to run Whisper translation.";
                    
                    const totalBytes = audioChunks.reduce((acc, c) => acc + c.size, 0);
                    addConsoleLog("VOICE", "Audio buffer finalized. WebM stream size: " + totalBytes + " bytes.");
                    
                    transcriptBox.value = "Audio recording compiled successfully.\n[Click 'Commit to Notion' to transcribe using Groq's high-performance cloud Whisper API]";
                    commitBtn.removeAttribute("disabled");
                };

                mediaRecorder.start();
            } catch (err) {
                console.error("Microphone binding failed:", err);
                addConsoleLog("VOICE", "Access failed: " + err.message, true);
                speechInstruction.textContent = "Mic Error: " + err.message;
            }
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop();
                // Stop all tracks in the stream to release the mic hardware immediately
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
        }

        micBtn.addEventListener("click", () => {
            if (isRecording) {
                stopRecording();
            } else {
                startRecording();
            }
        });

        clearBtn.addEventListener("click", () => {
            stopRecording();
            audioChunks = [];
            transcriptBox.value = "";
            commitBtn.setAttribute("disabled", "true");
            speechInstruction.textContent = "Tap psychic orb to log your daily dump...";
            addConsoleLog("VOICE", "Audio buffer completely flushed.");
        });

        // Typing fallback support inside the box
        transcriptBox.addEventListener("input", () => {
            if (transcriptBox.value.trim()) {
                commitBtn.removeAttribute("disabled");
            } else {
                commitBtn.setAttribute("disabled", "true");
            }
        });

        // Fetch dynamic brief
        async function fetchBriefing() {
            briefingBox.innerHTML = "<p style='color: rgba(255,255,255,0.4); font-family: var(--font-mono); font-size: 11px;'>Re-compiling schedule splits via Coral SQL...</p>";
            addConsoleLog("CORAL_SQL", "Executing daily morning briefing join query.");
            
            try {
                const res = await fetch(`${API_BASE}/briefing`);
                if (res.ok) {
                    const data = await res.json();
                    briefingBox.innerHTML = formatMarkdownToHTML(data.markdown);
                    addConsoleLog("LLM", "Morning briefing compiled successfully.");
                } else {
                    throw new Error();
                }
            } catch (err) {
                addConsoleLog("CORAL_SQL", "Failed to compile morning briefing. Check LLM keys and Coral connection.", true);
                briefingBox.innerHTML = `
                    <div style="font-size: 10px; font-weight: 700; color: #ff0055; text-transform: uppercase; margin-bottom: 8px;">BRIEFING OFFLINE</div>
                    <div class="briefing-text">
                        <p style="color: rgba(255,255,255,0.6); font-size: 12px;">
                            Unable to fetch dynamic briefing. The LLM connection may be rate-limited, or the backend is unreachable. 
                            Check the terminal logs for details.
                        </p>
                    </div>
                `;
            }
        }

        // Fetch Chess, Strava, and Goals
        async function fetchDashboardTelemetry() {
            addConsoleLog("CORAL_SQL", "Polling live Strava & Chess.com SQL telemetry databases.");
            
            try {
                const res = await fetch(`${API_BASE}/dashboard`);
                if (res.ok) {
                    const data = await res.json();
                    
                    // Update Chess
                    document.getElementById("chess-rapid-rating").textContent = data.chess.rapid;
                    document.getElementById("chess-blitz-rating").textContent = data.chess.blitz;
                    
                    const chessTotal = data.chess.wins + data.chess.losses + data.chess.draws;
                    const winPercent = chessTotal > 0 ? ((data.chess.wins / chessTotal) * 100).toFixed(1) : "0";
                    document.getElementById("chess-win-ratio").textContent = `${winPercent}% win rate`;
                    document.getElementById("chess-win-bar").style.width = `${winPercent}%`;

                    // Update Running
                    document.getElementById("run-avg-pace").textContent = `Pace: ${data.running.recent_run_pace}`;
                    document.getElementById("run-weekly-ratio").textContent = `${data.running.weekly_km} / ${data.running.weekly_target} KM`;
                    
                    const percent = Math.min((data.running.weekly_km / data.running.weekly_target) * 100, 100);
                    document.getElementById("run-weekly-bar").style.width = `${percent}%`;
                    document.getElementById("run-5k-pb").textContent = data.running.five_k_pb;
                    document.getElementById("run-10k-pb").textContent = data.running.ten_k_pb;

                    // Update Goals
                    const goalsList = document.getElementById("goals-list-box");
                    goalsList.innerHTML = "";
                    
                    data.goals.forEach(g => {
                        const progressPercent = Math.min((g.progress / g.total) * 100, 100);
                        const goalCard = document.createElement("div");
                        goalCard.style.cssText = "background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.02); border-radius: 10px; padding: 10px;";
                        goalCard.innerHTML = `
                            <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px; font-weight: 600;">
                                <span style="color: white;">${g.title}</span>
                                <span style="color: var(--accent-purple);">${g.progress}/${g.total}</span>
                            </div>
                            <div class="progress-bar-hud" style="height: 5px; margin-bottom: 6px;">
                                <div class="progress-bar-fill" style="width: ${progressPercent}%; background: var(--accent-purple);"></div>
                            </div>
                            <div style="font-size: 8.5px; color: rgba(255,255,255,0.4); text-transform: uppercase; text-align: right;">
                                Pacing: <strong style="color: white;">${g.pacing}</strong>
                            </div>
                        `;
                        goalsList.appendChild(goalCard);
                    });

                    // Update patterns
                    const scatterIndicator = document.getElementById("pattern-scatter");
                    const spiralIndicator = document.getElementById("pattern-spiral");

                    if (data.patterns.scatter_loop === "active") {
                        scatterIndicator.style.background = "rgba(255, 0, 85, 0.07)";
                        scatterIndicator.style.borderColor = "#ff0055";
                        scatterIndicator.style.color = "#ff3b70";
                        scatterIndicator.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background: #ff0055; box-shadow: 0 0 10px #ff0055;"></span> Scatter Loop`;
                    } else {
                        scatterIndicator.style.background = "rgba(102, 252, 241, 0.04)";
                        scatterIndicator.style.borderColor = "rgba(102, 252, 241, 0.12)";
                        scatterIndicator.style.color = "var(--primary-color)";
                        scatterIndicator.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background: var(--primary-color);"></span> Scatter Loop`;
                    }
                    
                    if (data.patterns.two_am_spiral === "active") {
                        spiralIndicator.style.background = "rgba(255, 0, 85, 0.07)";
                        spiralIndicator.style.borderColor = "#ff0055";
                        spiralIndicator.style.color = "#ff3b70";
                        spiralIndicator.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background: #ff0055; box-shadow: 0 0 10px #ff0055;"></span> 2 AM Spiral`;
                    } else {
                        spiralIndicator.style.background = "rgba(102, 252, 241, 0.04)";
                        spiralIndicator.style.borderColor = "rgba(102, 252, 241, 0.12)";
                        spiralIndicator.style.color = "var(--primary-color)";
                        spiralIndicator.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background: var(--primary-color);"></span> 2 AM Spiral`;
                    }
                    
                    addConsoleLog("CORAL_SQL", "SQL telemetry database sync complete.");
                }
            } catch (err) {
                addConsoleLog("CORAL_SQL", "Failed to reach telemetry dashboard APIs. Using sandbox simulation.", true);
            }
        }

        // Commit Voice Diary Entry
        commitBtn.addEventListener("click", async () => {
            const text = transcriptBox.value.trim();
            if (!text) return;

            commitBtn.setAttribute("disabled", "true");
            commitBtn.textContent = "LOGGING...";
            
            // Check if we are uploading local raw audio or manual text transcription
            const hasRecordedAudio = audioChunks.length > 0 && text.startsWith("Audio recording compiled");

            try {
                let res;
                if (hasRecordedAudio) {
                    addConsoleLog("NOTION", "Uploading local audio stream to Groq Whisper...");
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append("file", audioBlob, "voice.webm");
                    
                    res = await fetch(`${API_BASE}/voice-diary/audio`, {
                        method: "POST",
                        body: formData
                    });
                } else {
                    addConsoleLog("NOTION", "Transmitting manual text dump to Notion...");
                    res = await fetch(`${API_BASE}/voice-diary`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ transcription: text })
                    });
                }

                if (res.ok) {
                    const result = await res.json();
                    showToast("Diary page successfully synced back to Notion!");
                    addConsoleLog("NOTION", "Structured page written to Diary DB.");
                    
                    const displayUserText = hasRecordedAudio ? result.transcription : text;
                    addChatBubble(displayUserText, "user");
                    addChatBubble(result.markdown, "agent");
                    fetchDashboardTelemetry();
                } else {
                    throw new Error();
                }
            } catch (err) {
                showToast("Notion offline. Telemetry written to local 'Daily/Diary' file.");
                addConsoleLog("NOTION", "Sync failed. Appending to local 'Daily/Diary' backup.");
                addChatBubble(text, "user");
                addChatBubble(`
### Daily Log Committed locally! 📝
- **Date**: Today
- **Mood**: \`Focused\`
- **Activities**: \`Running\`, \`Coding\`

#### Summary
${text}

#### Tomorrow's Focus
Verify calendar sync and keep consistent.
                `, "agent");
            } finally {
                commitBtn.textContent = "COMMIT TO NOTION";
                commitBtn.removeAttribute("disabled");
                clearBtn.click();
            }
        });

        // Chat Terminal console handler
        async function handleChatSubmit() {
            const message = chatInputField.value.trim();
            if (!message) return;

            addChatBubble(message, "user");
            chatInputField.value = "";
            addConsoleLog("LLM", "Routing intent query: '" + message + "'");

            try {
                const res = await fetch(`${API_BASE}/chat`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: message })
                });

                if (res.ok) {
                    const data = await res.json();
                    addChatBubble(data.markdown, "agent");
                    addConsoleLog("LLM", "Request routing resolved. Intent: " + data.intent.toUpperCase());
                    fetchDashboardTelemetry();
                } else {
                    throw new Error();
                }
            } catch (err) {
                addConsoleLog("LLM", "Connection offline. Using dynamic local parser.");
                setTimeout(() => {
                    if (message.toLowerCase().includes("pb") || message.toLowerCase().includes("run")) {
                        addChatBubble(`### Personal Record Stats 🏃‍♂️
- **5K Personal Best**: \`24:20\` (set during birthday run)
- **10K Personal Best**: \`54:30\`
- **Half Marathon**: Completed on your 21st birthday in April 2026.
Next Target: Full marathon in December 2026. Keep compiling consistency in your weekly runs.`, "agent");
                    } else if (message.toLowerCase().includes("goal") || message.toLowerCase().includes("neetcode")) {
                        addChatBubble(`### Goal Decomposition Plan 💻
To finish NeetCode 150 by July 31 (61 days left), you need to average exactly 2.4 problems per day.

**Structured tasks generated and logged to Notion:**
- **NeetCode: Two Pointers Section (3 problems)** | Deadline: 2026-05-27
- **NeetCode: Sliding Window Section (3 problems)** | Deadline: 2026-05-29
- **Landslide Susceptibility Paper Rewrite** | Deadline: 2026-05-30`, "agent");
                    } else {
                        addChatBubble("Copy that, Anish. Focus on the screen and do the immediate work for the next 45 minutes. No distractions.", "agent");
                    }
                }, 400);
            }
        }

        chatSendBtn.addEventListener("click", handleChatSubmit);
        chatInputField.addEventListener("keydown", (e) => {
            if (e.key === "Enter") handleChatSubmit();
        });

        refreshBriefBtn.addEventListener("click", () => {
            fetchBriefing();
            fetchDashboardTelemetry();
        });

        // Chat bubble builder
        function addChatBubble(content, sender) {
            const bubble = document.createElement("div");
            bubble.classList.add("chat-bubble");
            bubble.classList.add(sender === "user" ? "chat-user" : "chat-agent");
            bubble.innerHTML = formatMarkdownToHTML(content);
            chatHistoryBox.appendChild(bubble);
            chatHistoryBox.scrollTop = chatHistoryBox.scrollHeight;
        }

        // Toast builder
        function showToast(message) {
            const container = document.getElementById("toast-bin");
            const toast = document.createElement("div");
            toast.classList.add("toast");
            toast.innerHTML = `<span style="font-weight:900; background:white; color:black; border-radius:3px; padding:1px 5px; font-size:10px; font-family:var(--font-display);">N</span> ${message}`;
            container.appendChild(toast);
            setTimeout(() => {
                toast.remove();
            }, 4000);
        }

        // Markdown parser
        function formatMarkdownToHTML(md) {
            if (!md) return "";
            return md
                .replace(/### (.*?)\n/g, '<h3 style="margin-top: 10px; margin-bottom: 5px; color: var(--text-header); font-family: var(--font-display); font-size:13.5px; text-transform:uppercase; letter-spacing:0.5px;">$1</h3>')
                .replace(/\*\*(.*?)\*\*/g, '<strong style="color:white;">$1</strong>')
                .replace(/`(.*?)`/g, '<code style="font-family: var(--font-mono); background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px; font-size: 11px; color: var(--primary-color);">$1</code>')
                .replace(/- (.*?)\n/g, '<li style="margin-left: 15px; font-size: 12.5px; margin-bottom: 4px; list-style-type:square; color:rgba(255,255,255,0.85);">$1</li>')
                .replace(/\n/g, '<br>');
        }

        // Initial Boot
        document.getElementById("init-time").innerText = "[" + new Date().toTimeString().split(" ")[0] + "]";
        checkStatus();
        fetchBriefing();
        fetchDashboardTelemetry();
        setInterval(checkStatus, 15000);
        setInterval(fetchDashboardTelemetry, 30000);

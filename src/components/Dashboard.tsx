import { useState, useRef, useEffect, useCallback } from 'react';
import { motion } from 'motion/react';
import { Mic, Send, Camera, Volume2, VolumeX, Globe } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import clsx from 'clsx';
import LiveMap from './LiveMap';
import DepartmentBadges from './DepartmentBadges';
import { sendChatMessage } from '../lib/gemini';

// ---------------------------------------------------------------------------
// Voice language options (SpeechRecognition lang codes)
// ---------------------------------------------------------------------------
const VOICE_LANGUAGES = [
  { code: 'en-IN', label: 'English' },
  { code: 'hi-IN', label: 'हिन्दी' },
  { code: 'ta-IN', label: 'தமிழ்' },
  { code: 'te-IN', label: 'తెలుగు' },
  { code: 'kn-IN', label: 'ಕನ್ನಡ' },
  { code: 'ml-IN', label: 'മലയാളം' },
  { code: 'bn-IN', label: 'বাংলা' },
  { code: 'mr-IN', label: 'मराठी' },
  { code: 'gu-IN', label: 'ગુજરાતી' },
] as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Message {
  id: string;
  role: 'user' | 'model' | 'system';
  content: string;
  timestamp: Date;
}

interface ExtractedData {
  incident_location: string | null;
  disaster_type: string | null;
  departments_required: string[];
  severity: string | null;
  extracted_entities: string[];
}

const INITIAL_DATA: ExtractedData = {
  incident_location: null,
  disaster_type: null,
  departments_required: [],
  severity: null,
  extracted_entities: [],
};

const API_BASE = 'http://localhost:8000';

// ---------------------------------------------------------------------------
// SpeechRecognition types (browser API)
// ---------------------------------------------------------------------------
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
}

const SpeechRecognition =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [extractedData, setExtractedData] = useState<ExtractedData>(INITIAL_DATA);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [voiceLang, setVoiceLang] = useState('en-IN');
  const [showLangPicker, setShowLangPicker] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatHistoryRef = useRef<Array<{ role: string; parts: Array<{ text: string }> }>>([]);
  const recognitionRef = useRef<any>(null);
  const audioEnabledRef = useRef(audioEnabled);
  audioEnabledRef.current = audioEnabled;

  // -----------------------------------------------------------------------
  // TTS — speak Anya's responses using browser SpeechSynthesis
  // -----------------------------------------------------------------------
  const speak = useCallback((text: string) => {
    if (!audioEnabledRef.current || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    // Auto-detect: if text contains Devanagari → Hindi, Tamil → Tamil, etc.
    const lang = /[\u0900-\u097F]/.test(text) ? 'hi-IN'
      : /[\u0B80-\u0BFF]/.test(text) ? 'ta-IN'
      : /[\u0C00-\u0C7F]/.test(text) ? 'te-IN'
      : /[\u0C80-\u0CFF]/.test(text) ? 'kn-IN'
      : /[\u0D00-\u0D7F]/.test(text) ? 'ml-IN'
      : 'en-IN';
    utterance.lang = lang;
    utterance.rate = 1.0;
    utterance.pitch = 1.1;
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find((v) => v.lang === lang)
      || voices.find((v) => v.lang.startsWith(lang.split('-')[0]));
    if (preferred) utterance.voice = preferred;
    window.speechSynthesis.speak(utterance);
  }, []);

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------
  const parseResponse = useCallback((text: string): string => {
    const jsonMatch = text.match(/```json\n([\s\S]*?)\n```/);
    if (!jsonMatch) return text;

    try {
      const jsonData = JSON.parse(jsonMatch[1]);
      setExtractedData((prev) => ({
        ...prev,
        ...jsonData,
        departments_required: [
          ...new Set([...(prev.departments_required || []), ...(jsonData.departments_required || [])]),
        ],
        extracted_entities: [
          ...new Set([...(prev.extracted_entities || []), ...(jsonData.extracted_entities || [])]),
        ],
      }));
      return text.replace(jsonMatch[0], '').trim();
    } catch {
      return text;
    }
  }, []);

  const addMessage = useCallback((role: 'user' | 'model' | 'system', content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: `${role}-${Date.now()}`, role, content, timestamp: new Date() },
    ]);
  }, []);

  // -----------------------------------------------------------------------
  // Send text to backend via REST
  // -----------------------------------------------------------------------
  const sendText = useCallback(async (text: string) => {
    chatHistoryRef.current.push({ role: 'user', parts: [{ text }] });
    addMessage('user', text);
    setIsProcessing(true);

    try {
      const result = await sendChatMessage(text, chatHistoryRef.current);
      const cleanText = parseResponse(result.text);
      chatHistoryRef.current.push({ role: 'model', parts: [{ text: result.text }] });
      addMessage('model', cleanText);
      speak(cleanText);
    } catch {
      addMessage('system', 'Connection error. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  }, [addMessage, parseResponse]);

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------
  useEffect(() => {
    addMessage('model', "This is Anya, 112 Emergency Response. I am listening. What is your emergency?");
  }, [addMessage]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // -----------------------------------------------------------------------
  // Text send
  // -----------------------------------------------------------------------
  const handleSend = async () => {
    const text = inputText.trim();
    if (!text) return;
    setInputText('');
    await sendText(text);
  };

  // -----------------------------------------------------------------------
  // Image upload via REST
  // -----------------------------------------------------------------------
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    addMessage('user', '📷 [Image Uploaded]');
    setIsProcessing(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/image`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`${res.status}`);

      const data = await res.json();
      const cleanText = parseResponse(data.text ?? '');
      addMessage('model', cleanText);
      speak(cleanText);
    } catch {
      addMessage('system', 'Failed to analyse the image. Please describe what you see.');
    } finally {
      setIsProcessing(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // -----------------------------------------------------------------------
  // Voice → uses browser SpeechRecognition to convert speech to text,
  // then sends the text to /chat via REST. No WebSocket needed.
  // -----------------------------------------------------------------------
  const startRecording = () => {
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Chrome.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = voiceLang;
    recognition.interimResults = false;
    recognition.continuous = false;
    recognitionRef.current = recognition;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0]?.[0]?.transcript;
      if (transcript) {
        sendText(transcript);
      }
    };

    recognition.onerror = () => {
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognition.start();
    setIsRecording(true);
  };

  const stopRecording = () => {
    recognitionRef.current?.stop();
    setIsRecording(false);
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="flex h-screen bg-black text-white font-sans overflow-hidden">
      {/* LEFT: Dashboard & Map */}
      <div className="flex-1 flex flex-col p-4 gap-4 max-w-[60%]">
        {/* Header */}
        <header className="flex items-center justify-between bg-zinc-900/80 p-4 rounded-2xl border border-white/10 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight">
              ANYA <span className="text-zinc-500 font-normal">| 112 DISPATCH</span>
            </h1>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-zinc-400">
            <span className="flex items-center gap-1 text-green-400">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              ONLINE
            </span>
            <span>UNIT: ALPHA-1</span>
            <span>{new Date().toLocaleTimeString()}</span>
          </div>
        </header>

        {/* Map Container */}
        <div className="flex-1 relative min-h-[400px]">
          <LiveMap
            location={extractedData.incident_location}
            coordinates={extractedData.incident_location ? [28.6139, 77.209] : undefined}
          />

          {/* Overlay Stats */}
          <div className="absolute bottom-4 left-4 right-4 z-[500] grid grid-cols-3 gap-2">
            <div className="bg-black/80 backdrop-blur-md p-3 rounded-lg border border-white/10">
              <div className="text-xs text-zinc-500 uppercase">Location</div>
              <div className="text-sm font-bold truncate">
                {extractedData.incident_location || 'Scanning…'}
              </div>
            </div>
            <div className="bg-black/80 backdrop-blur-md p-3 rounded-lg border border-white/10">
              <div className="text-xs text-zinc-500 uppercase">Type</div>
              <div className="text-sm font-bold text-red-400">
                {extractedData.disaster_type || 'Analysing…'}
              </div>
            </div>
            <div className="bg-black/80 backdrop-blur-md p-3 rounded-lg border border-white/10">
              <div className="text-xs text-zinc-500 uppercase">Entities</div>
              <div className="text-xs text-zinc-300 truncate">
                {extractedData.extracted_entities.join(', ') || 'None detected'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT: Chat & Controls */}
      <div className="w-[40%] flex flex-col bg-zinc-900 border-l border-white/5">
        {/* Status Panel */}
        <div className="p-6 border-b border-white/5 bg-zinc-900/50">
          <DepartmentBadges
            departments={extractedData.departments_required}
            severity={extractedData.severity}
          />
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx(
                'flex flex-col max-w-[85%]',
                msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'
              )}
            >
              <div
                className={clsx(
                  'p-3 rounded-2xl text-sm leading-relaxed',
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : msg.role === 'system'
                    ? 'bg-red-900/50 text-red-200 border border-red-500/20'
                    : 'bg-zinc-800 text-zinc-200 rounded-bl-none border border-white/5'
                )}
              >
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
              <span className="text-[10px] text-zinc-600 mt-1 px-1">
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </motion.div>
          ))}

          {isProcessing && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="self-start bg-zinc-800 p-3 rounded-2xl rounded-bl-none border border-white/5"
            >
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-black border-t border-white/10">
          <div className="flex items-center gap-2 bg-zinc-900 p-2 rounded-full border border-white/10 focus-within:border-blue-500/50 transition-colors">
            <button
              onClick={() => { setAudioEnabled(!audioEnabled); if (audioEnabled) window.speechSynthesis.cancel(); }}
              className={clsx(
                'p-2 rounded-full transition-colors',
                audioEnabled ? 'text-zinc-400 hover:text-white' : 'text-red-500 hover:text-red-400'
              )}
              title={audioEnabled ? 'Mute voice' : 'Unmute voice'}
            >
              {audioEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
            </button>

            {/* Language picker */}
            <div className="relative">
              <button
                onClick={() => setShowLangPicker(!showLangPicker)}
                className="p-2 text-zinc-400 hover:text-white transition-colors rounded-full flex items-center gap-1"
                title="Voice language"
              >
                <Globe size={18} />
                <span className="text-[10px] font-mono uppercase">{voiceLang.split('-')[0]}</span>
              </button>
              {showLangPicker && (
                <div className="absolute bottom-full mb-2 left-0 bg-zinc-800 border border-white/10 rounded-xl p-1 shadow-xl z-50 min-w-[130px]">
                  {VOICE_LANGUAGES.map((l) => (
                    <button
                      key={l.code}
                      onClick={() => { setVoiceLang(l.code); setShowLangPicker(false); }}
                      className={clsx(
                        'w-full text-left px-3 py-1.5 text-xs rounded-lg transition-colors',
                        voiceLang === l.code
                          ? 'bg-blue-600 text-white'
                          : 'text-zinc-300 hover:bg-zinc-700'
                      )}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <input
              type="file"
              accept="image/*"
              className="hidden"
              ref={fileInputRef}
              onChange={handleImageUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-zinc-400 hover:text-white transition-colors"
              title="Upload Image"
            >
              <Camera size={20} />
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type or hold mic to speak…"
              className="flex-1 bg-transparent border-none outline-none text-white placeholder-zinc-600 text-sm px-2"
              disabled={isRecording || isProcessing}
            />

            <button
              onMouseDown={startRecording}
              onMouseUp={stopRecording}
              onMouseLeave={stopRecording}
              onTouchStart={startRecording}
              onTouchEnd={stopRecording}
              className={clsx(
                'p-3 rounded-full transition-all duration-200',
                isRecording
                  ? 'bg-red-500 text-white scale-110 shadow-[0_0_20px_rgba(239,68,68,0.5)]'
                  : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
              )}
            >
              <Mic size={20} />
            </button>

            <button
              onClick={handleSend}
              disabled={!inputText.trim() || isProcessing}
              className="p-3 bg-blue-600 text-white rounded-full hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send size={20} />
            </button>
          </div>
          <div className="text-center mt-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-widest">
              {isRecording ? 'Listening…' : `Hold mic to speak · ${VOICE_LANGUAGES.find(l => l.code === voiceLang)?.label ?? voiceLang}`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

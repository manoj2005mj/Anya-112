import { useState, useRef, useEffect, useCallback } from 'react';
import { motion } from 'motion/react';
import { Send, Camera, Volume2, VolumeX, Globe, Phone } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import clsx from 'clsx';
import LiveMap from './LiveMap';
import DepartmentBadges from './DepartmentBadges';
import RoutingAlert from './RoutingAlert';
import { sendChatMessage } from '../lib/gemini';
import { getEmergencyRoute, RoutingResponse } from '../lib/routing';

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
  coordinates: [number, number] | null;
  disaster_type: string | null;
  departments_required: string[];
  severity: string | null;
  extracted_entities: string[];
}

const INITIAL_DATA: ExtractedData = {
  incident_location: null,
  coordinates: null,
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

function normalizeSeverity(severity: string | null | undefined): string | null {
  if (!severity) return null;
  const normalized = severity.trim().toLowerCase();
  if (normalized === 'low') return 'Low';
  if (normalized === 'medium' || normalized === 'moderate') return 'Medium';
  if (normalized === 'high') return 'High';
  if (normalized === 'critical' || normalized === 'severe') return 'Critical';
  return severity.trim();
}

function normalizeDepartment(department: string): string {
  const normalized = department.trim().toLowerCase();
  if (normalized.includes('fire')) return 'Fire';
  if (normalized.includes('ambulance') || normalized.includes('medical') || normalized.includes('hospital') || normalized.includes('paramedic')) return 'Ambulance';
  if (normalized.includes('police') || normalized.includes('law')) return 'Police';
  if (normalized.includes('electric') || normalized.includes('power') || normalized.includes('utility')) return 'Electrical';
  if (normalized.includes('disaster') || normalized.includes('rescue') || normalized.includes('ndrf')) return 'Disaster Response';
  return department.trim();
}

function normalizeCoordinates(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) return null;
  const lat = Number(value[0]);
  const lng = Number(value[1]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return [lat, lng];
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function normalizeExtractedData(input: Partial<ExtractedData>): Partial<ExtractedData> {
  return {
    incident_location: input.incident_location?.trim() || null,
    coordinates: normalizeCoordinates(input.coordinates),
    disaster_type: input.disaster_type?.trim() || null,
    departments_required: uniqueStrings((input.departments_required || []).map(normalizeDepartment)),
    severity: normalizeSeverity(input.severity),
    extracted_entities: uniqueStrings((input.extracted_entities || []).map((entity) => entity.trim())),
  };
}

function extractJsonPayload(text: string): Record<string, unknown> | null {
  const fencedMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fencedMatch) {
    try {
      return JSON.parse(fencedMatch[1]);
    } catch {
      return null;
    }
  }

  const firstBrace = text.indexOf('{');
  const lastBrace = text.lastIndexOf('}');
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    try {
      return JSON.parse(text.slice(firstBrace, lastBrace + 1));
    } catch {
      return null;
    }
  }

  return null;
}

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

  // Routing state
  const [routingData, setRoutingData] = useState<RoutingResponse | null>(null);
  const [showRoutingAlert, setShowRoutingAlert] = useState(false);
  const routingRequestKeyRef = useRef<string | null>(null);

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
  // Fetch routing data when location and disaster type are available
  // -----------------------------------------------------------------------
  useEffect(() => {
    const fetchRoutingData = async () => {
      if (
        extractedData.coordinates &&
        extractedData.disaster_type
      ) {
        const [lat, lng] = extractedData.coordinates;
        const nextKey = `${lat}:${lng}:${extractedData.disaster_type}`;
        if (routingRequestKeyRef.current === nextKey) return;
        routingRequestKeyRef.current = nextKey;

        const result = await getEmergencyRoute(
          lat,
          lng,
          extractedData.disaster_type
        );

        if (result) {
          setRoutingData(result);
          // Show alert after a short delay
          setTimeout(() => setShowRoutingAlert(true), 500);
        }
      }
    };

    fetchRoutingData();
  }, [extractedData.coordinates, extractedData.disaster_type]);

  useEffect(() => {
    if (!extractedData.coordinates || !extractedData.disaster_type) {
      routingRequestKeyRef.current = null;
      setRoutingData(null);
      setShowRoutingAlert(false);
    }
  }, [extractedData.coordinates, extractedData.disaster_type]);

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------
  const parseResponse = useCallback((text: string): string => {
    const jsonData = extractJsonPayload(text);
    if (jsonData) {
      const normalized = normalizeExtractedData(jsonData as Partial<ExtractedData>);
      setExtractedData((prev) => ({
        ...prev,
        ...normalized,
        departments_required: uniqueStrings([
          ...(prev.departments_required || []),
          ...(normalized.departments_required || []),
        ]),
        extracted_entities: uniqueStrings([
          ...(prev.extracted_entities || []),
          ...(normalized.extracted_entities || []),
        ]),
      }));
    }

    return text.replace(/```(?:json)?\s*[\s\S]*?```/i, '').trim();
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
  }, [addMessage, parseResponse, speak]);

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
  // Continuous recording mode for call-style interaction.
  // -----------------------------------------------------------------------
  const startRecording = () => {
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Chrome.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = voiceLang;
    recognition.interimResults = false;
    recognition.continuous = true; // Keep recording continuously
    recognitionRef.current = recognition;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      // Get the latest result
      const resultIndex = event.results.length - 1;
      const transcript = event.results[resultIndex]?.[0]?.transcript;
      if (transcript && event.results[resultIndex].isFinal) {
        sendText(transcript);
      }
    };

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      // Don't stop recording on error, try to recover
      if (event.error === 'no-speech') {
        // Restart recognition if no speech detected
        try {
          recognition.start();
        } catch (e) {
          // Ignore if already started
        }
      } else {
        setIsRecording(false);
      }
    };

    recognition.onend = () => {
      // Auto-restart if we're still in recording mode (call hasn't ended)
      if (isRecording) {
        try {
          recognition.start();
        } catch (e) {
          // If we can't restart, stop recording
          setIsRecording(false);
        }
      }
    };

    recognition.start();
    setIsRecording(true);
  };

  const stopRecording = () => {
    setIsRecording(false);
    recognitionRef.current?.stop();
    recognitionRef.current = null;
  };

  const toggleCall = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="flex h-screen bg-zinc-50 text-zinc-900 font-sans overflow-hidden">
      {/* LEFT: Dashboard & Map */}
      <div className="flex-1 flex flex-col p-4 gap-4 max-w-[60%]">
        {/* Header */}
        <header className="flex items-center justify-between bg-white p-4 rounded-2xl border border-zinc-200 shadow-sm backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-red-600 rounded-full animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight">
              ANYA <span className="text-zinc-400 font-normal">| 112 DISPATCH</span>
            </h1>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-zinc-500">
            <span className="flex items-center gap-1 text-green-600">
              <span className="w-2 h-2 rounded-full bg-green-500" />
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
            coordinates={extractedData.coordinates || undefined}
            facilityCoordinates={routingData?.facility.coordinates}
            facilityName={routingData?.facility.name}
            routeGeometry={routingData?.route.geometry || undefined}
          />

          {/* Overlay Stats */}
          <div className="absolute bottom-4 left-4 right-4 z-[500] grid grid-cols-3 gap-2">
            <div className="bg-white/90 backdrop-blur-md p-3 rounded-xl border border-zinc-200 shadow-lg">
              <div className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Location</div>
              <div className="text-sm font-bold truncate text-zinc-800">
                {extractedData.incident_location || 'Scanning…'}
              </div>
            </div>
            <div className="bg-white/90 backdrop-blur-md p-3 rounded-xl border border-zinc-200 shadow-lg">
              <div className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Type</div>
              <div className="text-sm font-bold text-red-600">
                {extractedData.disaster_type || 'Analysing…'}
              </div>
            </div>
            <div className="bg-white/90 backdrop-blur-md p-3 rounded-xl border border-zinc-200 shadow-lg">
              <div className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Entities</div>
              <div className="text-xs text-zinc-600 truncate">
                {extractedData.extracted_entities.join(', ') || 'None detected'}
              </div>
            </div>
          </div>

          {/* ETA Badge (shown when routing is available) */}
          {routingData && (
            <div className="absolute top-4 left-4 z-[500] bg-green-500/90 text-white px-4 py-2 rounded-xl shadow-lg backdrop-blur-sm">
              <div className="text-xs font-semibold uppercase tracking-wider">ETA</div>
              <div className="text-xl font-bold">{Math.round(routingData.route.duration_min)} min</div>
            </div>
          )}
        </div>
      </div>

      {/* RIGHT: Chat & Controls */}
      <div className="w-[40%] flex flex-col bg-white border-l border-zinc-200">
        {/* Status Panel */}
        <div className="p-6 border-b border-zinc-100 bg-zinc-50/50">
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
                  'p-3 rounded-2xl text-sm leading-relaxed shadow-sm',
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : msg.role === 'system'
                      ? 'bg-red-50 text-red-700 border border-red-200'
                      : 'bg-zinc-100 text-zinc-800 rounded-bl-none border border-zinc-200'
                )}
              >
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
              <span className="text-[10px] text-zinc-400 mt-1 px-1">
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </motion.div>
          ))}

          {isProcessing && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="self-start bg-zinc-100 p-3 rounded-2xl rounded-bl-none border border-zinc-200"
            >
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-zinc-50 border-t border-zinc-200">
          <div className="flex items-center gap-2 bg-white p-2 rounded-full border border-zinc-300 shadow-sm focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-200 transition-all">
            <button
              onClick={() => { setAudioEnabled(!audioEnabled); if (audioEnabled) window.speechSynthesis.cancel(); }}
              className={clsx(
                'p-2 rounded-full transition-colors',
                audioEnabled ? 'text-zinc-400 hover:text-zinc-600' : 'text-red-500 hover:text-red-600'
              )}
              title={audioEnabled ? 'Mute voice' : 'Unmute voice'}
            >
              {audioEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
            </button>

            {/* Language picker */}
            <div className="relative">
              <button
                onClick={() => setShowLangPicker(!showLangPicker)}
                className="p-2 text-zinc-400 hover:text-zinc-600 transition-colors rounded-full flex items-center gap-1"
                title="Voice language"
              >
                <Globe size={18} />
                <span className="text-[10px] font-mono uppercase font-bold">{voiceLang.split('-')[0]}</span>
              </button>
              {showLangPicker && (
                <div className="absolute bottom-full mb-2 left-0 bg-white border border-zinc-200 rounded-xl p-1 shadow-2xl z-50 min-w-[130px]">
                  {VOICE_LANGUAGES.map((l) => (
                    <button
                      key={l.code}
                      onClick={() => { setVoiceLang(l.code); setShowLangPicker(false); }}
                      className={clsx(
                        'w-full text-left px-3 py-1.5 text-xs rounded-lg transition-colors',
                        voiceLang === l.code
                          ? 'bg-blue-600 text-white'
                          : 'text-zinc-600 hover:bg-zinc-100'
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
              className="p-2 text-zinc-400 hover:text-zinc-600 transition-colors"
              title="Upload Image"
            >
              <Camera size={20} />
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type or tap the call button to speak…"
              className="flex-1 bg-transparent border-none outline-none text-zinc-800 placeholder-zinc-400 text-sm px-2"
              disabled={isRecording || isProcessing}
            />

            <button
              onClick={toggleCall}
              className={clsx(
                'p-3 rounded-full transition-all duration-200',
                isRecording
                  ? 'bg-green-500 text-white scale-110 shadow-[0_0_20px_rgba(34,197,94,0.3)]'
                  : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700'
              )}
              title={isRecording ? 'End call' : 'Start call'}
            >
              <Phone size={20} fill={isRecording ? 'white' : 'none'} />
            </button>

            <button
              onClick={handleSend}
              disabled={!inputText.trim() || isProcessing}
              className="p-3 bg-blue-600 text-white rounded-full hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-md shadow-blue-200"
            >
              <Send size={20} />
            </button>
          </div>
          <div className="text-center mt-2">
            <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-widest">
              {isRecording ? `📞 Call in progress · ${VOICE_LANGUAGES.find(l => l.code === voiceLang)?.label ?? voiceLang}` : `Tap to start call · ${VOICE_LANGUAGES.find(l => l.code === voiceLang)?.label ?? voiceLang}`}
            </span>
          </div>
        </div>
      </div>

      {/* Routing Alert Modal */}
      <RoutingAlert
        show={showRoutingAlert}
        facility={routingData?.facility || null}
        route={routingData?.route || null}
        onClose={() => setShowRoutingAlert(false)}
      />
    </div>
  );
}

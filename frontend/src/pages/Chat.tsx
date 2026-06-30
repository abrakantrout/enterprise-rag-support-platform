import React, { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';
import type { ChatSession, ChatMessage } from '../api/client';
import { 
  MessageSquare, 
  Plus, 
  Send, 
  ShieldCheck, 
  ShieldAlert, 
  BookOpen,
  ThumbsUp,
  ThumbsDown,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Clock,
  Sparkles
} from 'lucide-react';

export const Chat: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [quotaError, setQuotaError] = useState<string | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);

  // Accordions
  const [openCitations, setOpenCitations] = useState<Record<string, boolean>>({});
  
  // Feedbacks
  const [openFeedback, setOpenFeedback] = useState<Record<string, boolean>>({});
  const [feedbackRating, setFeedbackRating] = useState<Record<string, 'thumbs_up' | 'thumbs_down'>>({});
  const [feedbackComment, setFeedbackComment] = useState<Record<string, string>>({});
  const [feedbackSuccess, setFeedbackSuccess] = useState<Record<string, string>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchSessions = async (selectLatest = false) => {
    try {
      const data = await api.listChatSessions();
      setSessions(data);
      if (data.length > 0 && (!currentSessionId || selectLatest)) {
        setCurrentSessionId(data[0].session_id);
      }
    } catch (err) {
      console.error(err);
      setGeneralError('Failed to fetch conversation history.');
    }
  };

  const fetchSessionMessages = async (sessionId: string) => {
    setSessionLoading(true);
    setQuotaError(null);
    setGeneralError(null);
    try {
      const data = await api.getChatSession(sessionId);
      setMessages(data.messages);
    } catch (err) {
      console.error(err);
      setGeneralError('Failed to load session messages.');
    } finally {
      setSessionLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    if (currentSessionId) {
      fetchSessionMessages(currentSessionId);
    } else {
      setMessages([]);
    }
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleCreateSession = async () => {
    try {
      const newSession = await api.createChatSession();
      await fetchSessions(true);
      setCurrentSessionId(newSession.session_id);
    } catch (err) {
      console.error(err);
      setGeneralError('Failed to create new chat session.');
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId || loading) return;

    const userText = input.trim();
    setInput('');
    setLoading(true);
    setQuotaError(null);
    setGeneralError(null);

    const localUserMsg: ChatMessage = {
      id: Math.random().toString(),
      session_id: currentSessionId,
      role: 'user',
      content: userText,
      created_at: new Date().toISOString()
    };
    setMessages((prev) => [...prev, localUserMsg]);

    try {
      await api.askQuestion(currentSessionId, userText);
      await fetchSessionMessages(currentSessionId);
    } catch (err: any) {
      console.error(err);
      const detail = err.response?.data?.detail || '';
      
      if (
        detail.toLowerCase().includes('quota') ||
        detail.toLowerCase().includes('limit') ||
        err.response?.status === 429
      ) {
        setQuotaError(
          '⚠️ Gemini API quota is exhausted. Knowledge retrieval works, but generating answers is blocked. Try again later.'
        );
      } else {
        setGeneralError(`Generation failed: ${detail || err.message}`);
      }
      
      fetchSessionMessages(currentSessionId);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedbackSubmit = async (messageId: string) => {
    const rating = feedbackRating[messageId];
    if (!rating) return;

    try {
      await api.submitFeedback(messageId, rating, feedbackComment[messageId]);
      setFeedbackSuccess((prev) => ({
        ...prev,
        [messageId]: 'Feedback received! Thank you.'
      }));
    } catch (err) {
      console.error(err);
    }
  };

  const toggleCitations = (msgId: string) => {
    setOpenCitations((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const toggleFeedbackBox = (msgId: string) => {
    setOpenFeedback((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  return (
    <div className="flex h-[calc(100vh-10rem)] bg-white border border-slate-200/85 rounded-2xl overflow-hidden shadow-sm font-sans">
      {/* Session Selection Left Sidebar */}
      <div className="w-80 bg-slate-50 border-r border-slate-200 flex flex-col justify-between shrink-0">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">Conversations</span>
          <button
            onClick={handleCreateSession}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-755 hover:to-indigo-755 rounded-xl text-xs font-bold text-white shadow-sm transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Sessions list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {sessions.length === 0 ? (
            <p className="text-xs text-slate-400 italic text-center p-4">No active conversations.</p>
          ) : (
            sessions.map((sess) => {
              const isSelected = sess.session_id === currentSessionId;
              return (
                <button
                  key={sess.session_id}
                  onClick={() => setCurrentSessionId(sess.session_id)}
                  className={`w-full text-left px-3.5 py-3 rounded-xl text-xs flex items-center justify-between transition-all duration-150 cursor-pointer ${
                    isSelected
                      ? 'bg-white border border-slate-200/80 font-bold text-violet-700 shadow-sm'
                      : 'hover:bg-slate-100 border border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <div className="flex items-center space-x-2.5 truncate">
                    <MessageSquare className={`w-4 h-4 shrink-0 ${isSelected ? 'text-violet-650' : 'text-slate-400'}`} />
                    <span className="truncate">Session {sess.session_id.slice(0, 8)}</span>
                  </div>
                  <ChevronRightIcon className="w-3 h-3 text-slate-350 shrink-0" />
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Main Conversation Feed */}
      <div className="flex-1 flex flex-col justify-between bg-slate-50/20">
        {/* Messages List Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {quotaError && (
            <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-start space-x-3 text-amber-800 shadow-sm">
              <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-xs font-bold uppercase tracking-wider">Quota Exhausted</p>
                <p className="text-xs leading-relaxed font-semibold">{quotaError}</p>
              </div>
            </div>
          )}

          {generalError && (
            <div className="bg-rose-50 border border-rose-200 p-4 rounded-xl flex items-start space-x-3 text-rose-800 shadow-sm">
              <AlertCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-xs font-bold uppercase tracking-wider">Service Error</p>
                <p className="text-xs leading-relaxed font-semibold">{generalError}</p>
              </div>
            </div>
          )}

          {!currentSessionId ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-2 text-center p-8">
              <MessageSquare className="w-8 h-8 text-slate-300" />
              <p className="text-sm font-semibold">Select or create a conversation to begin testing.</p>
            </div>
          ) : sessionLoading ? (
            <div className="h-full flex items-center justify-center space-x-2 text-slate-400">
              <Clock className="w-5 h-5 animate-spin" />
              <span className="text-xs font-semibold">Retrieving session messages...</span>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-405 text-slate-400 space-y-2 text-center p-8">
              <Sparkles className="w-8 h-8 text-violet-200" />
              <p className="text-xs font-semibold">Send a customer policy inquiry below to test grounding verification.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg) => {
                const isUser = msg.role === 'user';
                return (
                  <div key={msg.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                    <div className="flex items-start space-x-3 max-w-2xl">
                      {!isUser && (
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-violet-650 to-indigo-650 flex items-center justify-center text-white shrink-0 shadow">
                          <Sparkles className="w-4 h-4" />
                        </div>
                      )}
                      
                      <div className={`rounded-2xl p-4 shadow-sm text-sm border leading-relaxed ${
                        isUser
                          ? 'bg-gradient-to-tr from-violet-600 to-indigo-600 text-white border-violet-500 rounded-tr-none'
                          : 'bg-white text-slate-800 border-slate-200/80 rounded-tl-none space-y-4'
                      }`}>
                        {/* Text */}
                        <div className="whitespace-pre-wrap">{msg.content}</div>

                        {/* Grounded Citation Accordion & Verification details */}
                        {!isUser && (
                          <div className="pt-3 border-t border-slate-100 space-y-3.5">
                            {/* Citations list */}
                            {msg.citations && msg.citations.length > 0 && (
                              <div className="border border-slate-200 bg-slate-50/50 rounded-xl overflow-hidden shadow-sm">
                                <button
                                  onClick={() => toggleCitations(msg.id)}
                                  className="w-full flex items-center justify-between px-3.5 py-2.5 bg-slate-50 text-slate-700 text-xs font-bold transition-colors hover:bg-slate-100 cursor-pointer"
                                >
                                  <div className="flex items-center space-x-2">
                                    <BookOpen className="w-3.5 h-3.5 text-violet-650" />
                                    <span>Grounded Citations ({msg.citations.length})</span>
                                  </div>
                                  {openCitations[msg.id] ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                                </button>
                                {openCitations[msg.id] && (
                                  <div className="p-3 bg-white space-y-3 divide-y divide-slate-100 max-h-48 overflow-y-auto">
                                    {msg.citations.map((cit, idx) => (
                                      <div key={idx} className="pt-2.5 first:pt-0 space-y-1 font-sans">
                                        <p className="text-[10px] font-bold text-slate-400">
                                          [{cit.source_label}] {cit.document_name} (Pg. {cit.page_number || 1}) • Similarity: <span className="text-violet-600 font-extrabold">{cit.similarity_score.toFixed(4)}</span>
                                        </p>
                                        <p className="text-xs text-slate-650 leading-relaxed italic">"{cit.text_preview}"</p>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Verification badging and rating */}
                            <div className="flex flex-wrap gap-3 items-center justify-between">
                              {msg.verification && (
                                <div className="flex items-center space-x-2.5 text-xs">
                                  {msg.verification.verification_status === 'verified' ? (
                                    <div className="flex items-center space-x-1 bg-emerald-50 border border-emerald-100 text-emerald-700 font-bold px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wide">
                                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                                      <span>Verified</span>
                                    </div>
                                  ) : (
                                    <div className="flex items-center space-x-1 bg-amber-50 border border-amber-100 text-amber-700 font-bold px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wide">
                                      <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
                                      <span>Unverified</span>
                                    </div>
                                  )}
                                  <span className="text-slate-350">•</span>
                                  <span className="text-slate-400 font-semibold">
                                    Confidence: <b className="text-slate-600">{(msg.verification.confidence * 100).toFixed(1)}%</b>
                                  </span>
                                </div>
                              )}

                              {/* Action rating icons */}
                              <div className="flex items-center space-x-1">
                                {feedbackSuccess[msg.id] ? (
                                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-100">
                                    {feedbackSuccess[msg.id]}
                                  </span>
                                ) : (
                                  <div className="flex items-center space-x-1 bg-slate-50 border border-slate-150 p-0.5 rounded-lg shadow-sm">
                                    <button
                                      onClick={() => {
                                        setFeedbackRating((prev) => ({ ...prev, [msg.id]: 'thumbs_up' }));
                                        toggleFeedbackBox(msg.id);
                                      }}
                                      className="p-1.5 hover:bg-white hover:shadow-sm rounded-md text-slate-400 hover:text-emerald-600 transition-all cursor-pointer"
                                    >
                                      <ThumbsUp className="w-3.5 h-3.5" />
                                    </button>
                                    <button
                                      onClick={() => {
                                        setFeedbackRating((prev) => ({ ...prev, [msg.id]: 'thumbs_down' }));
                                        toggleFeedbackBox(msg.id);
                                      }}
                                      className="p-1.5 hover:bg-white hover:shadow-sm rounded-md text-slate-400 hover:text-rose-600 transition-all cursor-pointer"
                                    >
                                      <ThumbsDown className="w-3.5 h-3.5" />
                                    </button>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Comment details popup */}
                            {openFeedback[msg.id] && !feedbackSuccess[msg.id] && (
                              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3 text-xs">
                                <p className="font-bold text-slate-700 uppercase tracking-wide text-[10px]">
                                  Rating: {feedbackRating[msg.id] === 'thumbs_up' ? '👍 Grounded & Useful' : '👎 Hallucinated / Out of Context'}
                                </p>
                                <input
                                  type="text"
                                  placeholder="Add details, e.g., missing citations, wrong fact..."
                                  value={feedbackComment[msg.id] || ''}
                                  onChange={(e) => setFeedbackComment((prev) => ({ ...prev, [msg.id]: e.target.value }))}
                                  className="block w-full border border-slate-200 bg-white rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-violet-500 text-xs text-slate-800 placeholder-slate-400 shadow-sm"
                                />
                                <div className="flex space-x-2 justify-end">
                                  <button
                                    onClick={() => setOpenFeedback((prev) => ({ ...prev, [msg.id]: false }))}
                                    className="px-3.5 py-1.5 border border-slate-250 hover:bg-white rounded-lg text-[10px] font-bold text-slate-600 transition-colors cursor-pointer"
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    onClick={() => handleFeedbackSubmit(msg.id)}
                                    className="px-3.5 py-1.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-lg text-[10px] font-bold shadow-sm transition-all cursor-pointer"
                                  >
                                    Submit
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              {loading && (
                <div className="flex justify-start">
                  <div className="flex items-start space-x-3 max-w-2xl">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-violet-650 to-indigo-650 flex items-center justify-center text-white shrink-0 shadow animate-pulse">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div className="bg-white border border-slate-200/80 rounded-2xl rounded-tl-none p-4 shadow-sm text-xs font-semibold text-slate-400 flex items-center space-x-2">
                      <Clock className="w-3.5 h-3.5 animate-spin" />
                      <span>Verifying ground sources...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input box */}
        <form onSubmit={handleSendMessage} className="p-4 bg-white border-t border-slate-200/80 flex items-center space-x-3.5">
          <input
            type="text"
            placeholder={currentSessionId ? "Ask a policy question..." : "Select conversation session to query..."}
            disabled={!currentSessionId || loading}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="flex-1 border border-slate-200 bg-slate-50 focus:bg-white rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm text-slate-800 placeholder-slate-400 shadow-inner transition-all disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!currentSessionId || loading || !input.trim()}
            className="p-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-750 hover:to-indigo-750 text-white rounded-xl shadow-md transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};

// Local inline helper icon since Lucide Chevron Right doesn't need to be imported again
const ChevronRightIcon = ({ className }: { className?: string }) => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    fill="none" 
    viewBox="0 0 24 24" 
    strokeWidth={2.5} 
    stroke="currentColor" 
    className={className}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
  </svg>
);

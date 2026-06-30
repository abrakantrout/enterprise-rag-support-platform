import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { 
  OverviewTelemetry, 
  RecentQuestion, 
  LowRatedAnswer 
} from '../api/client';
import { 
  FileText, 
  MessageSquare, 
  ThumbsDown, 
  CheckCircle,
  AlertCircle,
  ThumbsUp,
  Clock,
  ChevronRight
} from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [overview, setOverview] = useState<OverviewTelemetry | null>(null);
  const [docStatusCounts, setDocStatusCounts] = useState<Record<string, number>>({});
  const [recentQuestions, setRecentQuestions] = useState<RecentQuestion[]>([]);
  const [lowRatedAnswers, setLowRatedAnswers] = useState<LowRatedAnswer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchTelemetry = async () => {
      setIsLoading(true);
      try {
        const [ov, ds, rq, lr] = await Promise.all([
          api.getOverview(),
          api.getDocumentStatusCounts(),
          api.getRecentQuestions(5),
          api.getLowRatedAnswers(5),
        ]);
        setOverview(ov);
        setDocStatusCounts(ds);
        setRecentQuestions(rq);
        setLowRatedAnswers(lr);
      } catch (err: any) {
        console.error(err);
        setError('Failed to refresh dashboard telemetry. Check your connection to the server.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTelemetry();
  }, []);

  const stats = [
    {
      name: 'Total Documents',
      value: overview?.total_documents ?? 0,
      icon: FileText,
      color: 'text-violet-600 bg-violet-50 border-violet-100',
    },
    {
      name: 'Processed Documents',
      value: docStatusCounts['Completed'] ?? 0,
      icon: CheckCircle,
      color: 'text-emerald-600 bg-emerald-50 border-emerald-100',
    },
    {
      name: 'Chat Sessions',
      value: overview?.total_chat_sessions ?? 0,
      icon: MessageSquare,
      color: 'text-blue-600 bg-blue-50 border-blue-100',
    },
    {
      name: 'Feedback Logs',
      value: overview?.total_feedback ?? 0,
      icon: ThumbsDown,
      color: 'text-amber-600 bg-amber-50 border-amber-100',
    },
  ];

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center space-x-2 text-slate-400">
        <Clock className="w-5 h-5 animate-spin" />
        <span className="text-sm font-semibold">Loading platform metrics...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8 font-sans">
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Platform Telemetry</h2>
        <p className="text-sm text-slate-500 mt-1">Review ingestion statuses, chat interactions, and response feedback scores.</p>
      </div>

      {error && (
        <div className="bg-rose-50 border border-rose-200 p-4 rounded-xl flex items-start space-x-3 text-rose-800 shadow-sm">
          <AlertCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          <span className="text-sm font-medium">{error}</span>
        </div>
      )}

      {/* Grid summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div 
              key={i} 
              className="bg-white border border-slate-200/80 rounded-xl p-6 shadow-sm flex items-center justify-between hover:shadow-md transition-all duration-150"
            >
              <div className="space-y-1">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">{stat.name}</p>
                <h3 className="text-2xl font-extrabold text-slate-800">{stat.value}</h3>
              </div>
              <div className={`p-3.5 rounded-xl border ${stat.color}`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Grounding Quality Summary Card */}
      {overview && (
        <div className="bg-white border border-slate-200/80 rounded-xl p-6 shadow-sm">
          <h4 className="text-sm font-bold text-slate-800 mb-5 pb-3 border-b border-slate-100 flex items-center space-x-2">
            <span>Grounding Quality & Statuses</span>
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Positive Feedbacks */}
            <div className="flex items-center space-x-4 p-4 bg-slate-50 rounded-xl border border-slate-100">
              <div className="p-3 bg-emerald-50 border border-emerald-100 text-emerald-600 rounded-xl shadow-sm">
                <ThumbsUp className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Positive Feedbacks</p>
                <p className="text-2xl font-extrabold text-slate-800 mt-1">{overview.thumbs_up_count}</p>
              </div>
            </div>

            {/* Negative Feedbacks */}
            <div className="flex items-center space-x-4 p-4 bg-slate-50 rounded-xl border border-slate-100">
              <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 rounded-xl shadow-sm">
                <ThumbsDown className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Negative Feedbacks</p>
                <p className="text-2xl font-extrabold text-slate-800 mt-1">{overview.thumbs_down_count}</p>
              </div>
            </div>

            {/* Ingestion statuses */}
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-2">
              <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Document pipeline status</p>
              <div className="space-y-2 pt-1.5">
                {Object.entries(docStatusCounts).map(([status, count]) => {
                  const isCompleted = status === 'Completed';
                  const isFailed = status === 'Failed';
                  return (
                    <div key={status} className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-650 text-slate-650">{status}</span>
                      <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                        isCompleted 
                          ? 'bg-emerald-50 text-emerald-700' 
                          : isFailed 
                          ? 'bg-rose-50 text-rose-700' 
                          : 'bg-amber-50 text-amber-700'
                      }`}>
                        {count} {count === 1 ? 'file' : 'files'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Details Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Queries */}
        <div className="bg-white border border-slate-200/80 rounded-xl p-6 shadow-sm flex flex-col">
          <h4 className="text-sm font-bold text-slate-850 text-slate-800 mb-4 pb-3 border-b border-slate-100">
            Recent Questions
          </h4>
          <div className="flex-1 space-y-3">
            {recentQuestions.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-xs italic">
                No customer queries logged yet.
              </div>
            ) : (
              recentQuestions.map((q) => (
                <div key={q.message_id} className="p-3 bg-slate-50 hover:bg-slate-100/50 rounded-xl border border-slate-150 transition-colors flex items-start space-x-3">
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wide">
                      Query • {new Date(q.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                    <p className="text-xs font-semibold text-slate-700 leading-relaxed">{q.content}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Negative Feedback logs */}
        <div className="bg-white border border-slate-200/80 rounded-xl p-6 shadow-sm flex flex-col">
          <h4 className="text-sm font-bold text-slate-850 text-slate-800 mb-4 pb-3 border-b border-slate-100">
            Low-Rated Responses
          </h4>
          <div className="flex-1 space-y-3">
            {lowRatedAnswers.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-xs italic">
                No negative feedback logs recorded.
              </div>
            ) : (
              lowRatedAnswers.map((item) => (
                <div key={item.feedback_id} className="p-4 bg-rose-50/20 hover:bg-rose-50/40 border border-rose-100 rounded-xl space-y-2.5 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wide">
                      Feedback • {new Date(item.created_at).toLocaleDateString()}
                    </span>
                    <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-100">
                      Score {item.score}/5
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed font-semibold italic">
                    "{item.answer.length > 120 ? `${item.answer.slice(0, 120)}...` : item.answer}"
                  </p>
                  {item.comment && (
                    <div className="bg-white p-2.5 rounded-lg border border-rose-50 text-[11px] leading-relaxed text-slate-600 shadow-sm">
                      <strong className="text-slate-800 font-semibold block text-[10px] uppercase tracking-wider text-rose-600 mb-1">
                        Agent Comment
                      </strong>
                      "{item.comment}"
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

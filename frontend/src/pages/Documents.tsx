import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DocumentMetadata, UserProfile } from '../api/client';
import { 
  UploadCloud, 
  CheckCircle2, 
  AlertCircle,
  Settings,
  ChevronDown,
  ChevronUp,
  Info,
  Trash2,
  FileText,
  Clock,
  Bookmark
} from 'lucide-react';

export const Documents: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [category, setCategory] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [globalSuccess, setGlobalSuccess] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(true);

  // Per-document status stages
  const [docStages, setDocStages] = useState<Record<string, {
    extracted: boolean;
    chunked: boolean;
    embedded: boolean;
    indexed: boolean;
  }>>({});

  // UI state toggles
  const [showManage, setShowManage] = useState<Record<string, boolean>>({});
  const [showDetails, setShowDetails] = useState<Record<string, boolean>>({});
  const [docFeedback, setDocFeedback] = useState<Record<string, { status: 'success' | 'error'; message: string }>>({});
  const [deletingDoc, setDeletingDoc] = useState<DocumentMetadata | null>(null);
  const [stepLoading, setStepLoading] = useState<Record<string, boolean>>({});

  const fetchDocuments = async (showSpinner = false) => {
    if (showSpinner) setListLoading(true);
    try {
      const data = await api.listDocuments(1, 50);
      setDocuments(data.items);

      const stages: typeof docStages = {};
      data.items.forEach((doc) => {
        const isCompleted = doc.status === 'Completed';
        const isExtracted = !!doc.extracted_at || isCompleted;
        stages[doc.id] = {
          extracted: isExtracted,
          chunked: false,
          embedded: false,
          indexed: false
        };
      });
      setDocStages(stages);
    } catch (err: any) {
      console.error(err);
      setGlobalError('Failed to retrieve document repository list.');
    } finally {
      setListLoading(false);
    }
  };

  useEffect(() => {
    const storedUser = localStorage.getItem('current_user');
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    fetchDocuments(true);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setGlobalError('Please select a support document to upload.');
      return;
    }

    setUploadLoading(true);
    setGlobalError(null);
    setGlobalSuccess(null);

    try {
      const newDoc = await api.uploadDocument(selectedFile, category || undefined);
      setGlobalSuccess(`Successfully registered and uploaded "${newDoc.filename}".`);
      setSelectedFile(null);
      setCategory('');
      fetchDocuments();
    } catch (err: any) {
      console.error(err);
      setGlobalError(err.response?.data?.detail || 'Failed to upload document.');
    } finally {
      setUploadLoading(false);
    }
  };

  const executePipelineStep = async (
    docId: string,
    step: 'extract' | 'chunk' | 'embed' | 'index'
  ) => {
    setDocFeedback((prev) => {
      const copy = { ...prev };
      delete copy[docId];
      return copy;
    });
    setStepLoading((prev) => ({ ...prev, [`${docId}_${step}`]: true }));

    try {
      if (step === 'extract') {
        await api.runExtraction(docId);
        setDocStages((prev) => ({
          ...prev,
          [docId]: { extracted: true, chunked: false, embedded: false, indexed: false }
        }));
        setDocFeedback((prev) => ({
          ...prev,
          [docId]: { status: 'success', message: 'Text extracted successfully! Next: Parse Chunks.' }
        }));
      } else if (step === 'chunk') {
        await api.runChunking(docId);
        setDocStages((prev) => ({
          ...prev,
          [docId]: { extracted: true, chunked: true, embedded: false, indexed: false }
        }));
        setDocFeedback((prev) => ({
          ...prev,
          [docId]: { status: 'success', message: 'Chunks generated successfully! Next: Generate Embeddings.' }
        }));
      } else if (step === 'embed') {
        await api.runEmbeddings(docId);
        setDocStages((prev) => ({
          ...prev,
          [docId]: { extracted: true, chunked: true, embedded: true, indexed: false }
        }));
        setDocFeedback((prev) => ({
          ...prev,
          [docId]: { status: 'success', message: 'Embeddings calculated! Next: Index Vectors.' }
        }));
      } else if (step === 'index') {
        await api.runIndexing(docId);
        setDocStages((prev) => ({
          ...prev,
          [docId]: { extracted: true, chunked: true, embedded: true, indexed: true }
        }));
        setDocFeedback((prev) => ({
          ...prev,
          [docId]: { status: 'success', message: 'Vector indexing completed successfully. Grounding active!' }
        }));
      }
      
      const updatedList = await api.listDocuments(1, 50);
      setDocuments(updatedList.items);
    } catch (err: any) {
      console.error(err);
      const detail = err.response?.data?.detail || err.message || 'Operation failed.';
      setDocFeedback((prev) => ({
        ...prev,
        [docId]: { status: 'error', message: `❌ Stage error: ${detail}` }
      }));
    } finally {
      setStepLoading((prev) => ({ ...prev, [`${docId}_${step}`]: false }));
    }
  };

  const handleDelete = async (docId: string) => {
    if (!deletingDoc) return;
    setGlobalError(null);
    setGlobalSuccess(null);

    try {
      await api.deleteDocument(docId);
      setGlobalSuccess(`Successfully removed document "${deletingDoc.filename}".`);
      
      setDocFeedback((prev) => {
        const copy = { ...prev };
        delete copy[docId];
        return copy;
      });
      
      setDeletingDoc(null);
      fetchDocuments();
    } catch (err: any) {
      console.error(err);
      setGlobalError(err.message || 'Failed to delete document.');
      setDeletingDoc(null);
    }
  };

  const toggleManage = (docId: string) => {
    setShowManage((prev) => ({ ...prev, [docId]: !prev[docId] }));
  };

  const toggleDetails = (docId: string) => {
    setShowDetails((prev) => ({ ...prev, [docId]: !prev[docId] }));
  };

  return (
    <div className="space-y-8 font-sans">
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Document Repository</h2>
        <p className="text-sm text-slate-500 mt-1">Upload support documentation files and orchestrate grounding pipelines.</p>
      </div>

      {globalSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-xl flex items-start space-x-3 text-emerald-800 shadow-sm animate-fade-in">
          <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
          <span className="text-xs font-bold leading-relaxed">{globalSuccess}</span>
        </div>
      )}

      {globalError && (
        <div className="bg-rose-50 border border-rose-250 border-rose-200 p-4 rounded-xl flex items-start space-x-3 text-rose-800 shadow-sm">
          <AlertCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          <span className="text-xs font-bold leading-relaxed">{globalError}</span>
        </div>
      )}

      {/* Upload Document Panel */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-sm">
        <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center space-x-2">
          <UploadCloud className="w-4 h-4 text-violet-600" />
          <span>Upload Support Policies</span>
        </h3>
        
        <form onSubmit={handleUpload} className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end">
          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              Select Document
            </label>
            <input
              type="file"
              required
              accept=".pdf,.txt,.docx"
              onChange={handleFileChange}
              className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-violet-50 file:text-violet-700 hover:file:bg-violet-100 transition-colors file:cursor-pointer"
            />
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              Category
            </label>
            <div className="relative">
              <input
                type="text"
                placeholder="e.g., Returns & Exchange"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="block w-full border border-slate-200 bg-slate-50 focus:bg-white rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-violet-500 text-xs text-slate-800 transition-all placeholder-slate-400"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={uploadLoading}
              className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white font-bold text-xs rounded-xl shadow-md transition-all cursor-pointer disabled:opacity-50"
            >
              {uploadLoading ? 'Uploading File...' : 'Upload Document'}
            </button>
          </div>
        </form>
      </div>

      {/* Pipeline listings */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-bold text-slate-800">Ingestion Pipelines</h4>
          <button 
            onClick={() => fetchDocuments(true)}
            className="text-xs font-bold text-violet-600 hover:text-violet-700 cursor-pointer"
          >
            Refresh List
          </button>
        </div>

        {listLoading ? (
          <div className="flex justify-center items-center h-48 text-slate-400">
            <Clock className="w-5 h-5 animate-spin mr-2" />
            <span className="text-xs font-semibold">Refreshing repository files...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="bg-white border border-slate-200/80 rounded-2xl p-10 text-center text-slate-400 text-xs italic">
            No source documents uploaded to the platform library.
          </div>
        ) : (
          <div className="space-y-4">
            {documents.map((doc) => {
              const stages = docStages[doc.id] || { extracted: false, chunked: false, embedded: false, indexed: false };
              const feedback = docFeedback[doc.id];
              const isCompleted = doc.status === 'Completed';
              
              // Define pipeline stage layout configurations
              const steps = [
                { key: 'extract', name: 'Extract Text', num: '1️⃣', active: true, done: stages.extracted },
                { key: 'chunk', name: 'Parse Chunks', num: '2️⃣', active: stages.extracted || isCompleted, done: stages.chunked },
                { key: 'embed', name: 'Embed Vectors', num: '3️⃣', active: stages.chunked, done: stages.embedded },
                { key: 'index', name: 'Index DB', num: '4️⃣', active: stages.embedded, done: stages.indexed },
              ];

              return (
                <div key={doc.id} className="bg-white border border-slate-200/80 hover:border-slate-300 rounded-2xl p-6 shadow-sm space-y-5 transition-all duration-150">
                  {/* File Metadata Details header */}
                  <div className="flex items-start justify-between flex-wrap gap-4">
                    <div className="flex items-center space-x-3.5">
                      <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl text-slate-450 text-slate-400">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-bold text-slate-800">{doc.filename}</span>
                          <span className={`px-2 py-0.5 rounded-full font-bold text-[9px] uppercase tracking-wider ${
                            doc.status === 'Completed'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                              : doc.status === 'Failed'
                              ? 'bg-rose-50 text-rose-700 border border-rose-100 animate-pulse'
                              : 'bg-amber-50 text-amber-700 border border-amber-100'
                          }`}>
                            {doc.status}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 font-medium">
                          File Type: <span className="font-bold text-slate-500 uppercase">{doc.file_type}</span> | 
                          Size: <span className="font-bold text-slate-500">{doc.file_size.toLocaleString()} bytes</span> | 
                          Uploaded: <span className="font-bold text-slate-500">{new Date(doc.created_at).toLocaleString()}</span>
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2 bg-slate-50 border border-slate-100 px-3.5 py-1.5 rounded-xl text-xs font-bold text-slate-650">
                      <Bookmark className="w-3.5 h-3.5 text-violet-500 shrink-0" />
                      <span>{doc.category || 'General'}</span>
                    </div>
                  </div>

                  {/* Stage-step status alerts */}
                  {feedback && (
                    <div className={`p-3.5 rounded-xl text-xs font-semibold border flex items-start space-x-2.5 ${
                      feedback.status === 'success' 
                        ? 'bg-emerald-50/50 border-emerald-100 text-emerald-800' 
                        : 'bg-rose-50/50 border-rose-100 text-rose-800'
                    }`}>
                      <Info className="w-4 h-4 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{feedback.message}</span>
                    </div>
                  )}

                  {/* Action step buttons row */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
                    {steps.map((st) => {
                      const isStepLoading = stepLoading[`${doc.id}_${st.key}`];
                      
                      if (st.done) {
                        return (
                          <div 
                            key={st.key} 
                            className="py-2.5 px-4 bg-emerald-50 border border-emerald-100 text-emerald-800 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 shadow-sm"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                            <span>{st.name}</span>
                          </div>
                        );
                      }

                      return (
                        <button
                          key={st.key}
                          onClick={() => executePipelineStep(doc.id, st.key as any)}
                          disabled={!st.active || isStepLoading}
                          className={`py-2.5 px-4 rounded-xl text-xs font-bold transition-all duration-150 text-center flex items-center justify-center space-x-1.5 shadow-sm ${
                            isStepLoading
                              ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                              : st.active
                              ? 'bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white cursor-pointer hover:shadow-md'
                              : 'bg-slate-50 border border-slate-150 text-slate-350 cursor-not-allowed shadow-none'
                          }`}
                        >
                          {isStepLoading && <Clock className="w-3.5 h-3.5 animate-spin shrink-0" />}
                          <span>{st.num} {st.name}</span>
                        </button>
                      );
                    })}

                    <button
                      onClick={() => toggleManage(doc.id)}
                      className={`py-2.5 px-4 border rounded-xl text-xs font-bold flex items-center justify-center space-x-2 transition-all duration-150 cursor-pointer ${
                        showManage[doc.id]
                          ? 'bg-slate-100 border-slate-300 text-slate-700'
                          : 'bg-white border-slate-250 border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      <Settings className="w-3.5 h-3.5 shrink-0" />
                      <span>Manage</span>
                      {showManage[doc.id] ? <ChevronUp className="w-3.5 h-3.5 shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 shrink-0" />}
                    </button>
                  </div>

                  {/* Collapsible details panel */}
                  {showManage[doc.id] && (
                    <div className="border border-slate-200 bg-slate-50/50 rounded-2xl p-5 space-y-4 animate-fade-in">
                      <div className="flex space-x-4">
                        <button
                          onClick={() => toggleDetails(doc.id)}
                          className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-bold text-slate-700 flex items-center space-x-1.5 transition-colors cursor-pointer"
                        >
                          <Info className="w-3.5 h-3.5 text-slate-500" />
                          <span>View System Attributes</span>
                        </button>

                        {(!user || user.role === 'Administrator') ? (
                          <button
                            onClick={() => setDeletingDoc(doc)}
                            className="px-4 py-2 bg-rose-50 border border-rose-200 hover:bg-rose-100 rounded-xl text-xs font-bold text-rose-700 flex items-center space-x-1.5 transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Delete Document</span>
                          </button>
                        ) : (
                          <button
                            disabled
                            className="px-4 py-2 bg-slate-100 border border-slate-200 rounded-xl text-xs font-bold text-slate-400 flex items-center space-x-1.5 cursor-not-allowed"
                          >
                            <span>🔒 Delete restricted</span>
                          </button>
                        )}
                      </div>

                      {showDetails[doc.id] && (
                        <div className="bg-white border border-slate-200 rounded-xl p-4 text-xs text-slate-650 text-slate-600 space-y-2 shadow-sm font-mono">
                          <p><b>DOCUMENT_ID:</b> <code className="text-violet-600">{doc.id}</code></p>
                          <p><b>STORAGE_PATH:</b> <code>{doc.stored_path}</code></p>
                          <p><b>VISIBILITY_ROLE:</b> {doc.visibility.toUpperCase()}</p>
                          <p><b>EXTRACTION_TIMESTAMP:</b> {doc.extracted_at ? new Date(doc.extracted_at).toLocaleString() : 'Not Extracted'}</p>
                          <p><b>CREATED_TIMESTAMP:</b> {new Date(doc.created_at).toLocaleString()}</p>
                          <p><b>UPDATE_TIMESTAMP:</b> {new Date(doc.updated_at).toLocaleString()}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {deletingDoc && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 border border-slate-200 space-y-6">
            <div>
              <h3 className="text-lg font-bold text-slate-900">Delete Knowledge Source</h3>
              <p className="text-sm text-slate-500 mt-2">
                You are about to permanently remove <strong>{deletingDoc.filename}</strong> from the grounding source library.
              </p>
            </div>
            
            <div className="bg-slate-50 border border-slate-100 p-4 rounded-xl space-y-2 text-xs text-slate-600">
              <p className="font-bold text-slate-700">Deleting this document will:</p>
              <ul className="list-disc pl-4 space-y-1.5 leading-relaxed">
                <li>Erase the source files from disk storage.</li>
                <li>Purge the text chunks parsed from this document.</li>
                <li>Remove all associated vector embeddings from ChromaDB.</li>
                <li>Prevent this document from influencing chat grounding responses.</li>
              </ul>
              <p className="mt-3 text-rose-600 font-bold">This action cannot be undone.</p>
            </div>

            <div className="flex space-x-3.5 pt-2">
              <button
                onClick={() => setDeletingDoc(null)}
                className="flex-1 py-2.5 border border-slate-200 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-50 hover:text-slate-800 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deletingDoc.id)}
                className="flex-1 py-2.5 bg-rose-600 hover:bg-rose-700 rounded-xl text-xs font-bold text-white shadow-md transition-colors cursor-pointer"
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

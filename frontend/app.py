import streamlit as st
import os
import time
from api_client import APIClient

# Page configuration
st.set_page_config(
    page_title="Enterprise AI Knowledge Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom CSS for premium enterprise styling
st.markdown("""
<style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Layout styling */
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.1rem;
        letter-spacing: -0.05rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #6B7280;
        font-weight: 500;
        margin-bottom: 1.5rem;
    }
    .divider {
        margin: 1rem 0;
        border-bottom: 1px solid #E5E7EB;
    }
    
    /* Premium components styling */
    div[data-testid="metric-container"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.07);
    }
    
    /* Status Badges */
    .badge {
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-processing {
        background-color: #FEF3C7;
        color: #92400E;
    }
    .badge-completed {
        background-color: #D1FAE5;
        color: #065F46;
    }
    .badge-failed {
        background-color: #FEE2E2;
        color: #991B1B;
    }
    
    /* Banner/Card panel */
    .card-panel {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize API Client and Session State
if "api_client" not in st.session_state:
    st.session_state.api_client = APIClient()

client = st.session_state.api_client

if "token" not in st.session_state:
    st.session_state.token = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# If token is stored, configure client
if st.session_state.token:
    client.set_token(st.session_state.token)
    if not st.session_state.current_user:
        try:
            st.session_state.current_user = client.get_me()
        except Exception:
            # Session expired/token invalid
            st.session_state.token = None
            st.session_state.current_user = None
            client.set_token(None)

# ----------------- LOGIN PAGE -----------------
def render_login_page():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 2.5rem; border-radius: 16px; text-align: center; color: white; margin-top: 3rem; margin-bottom: 1.5rem;">
            <h2 style="margin: 0; font-weight: 800; font-size: 1.8rem;">Enterprise RAG Support</h2>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9; font-size: 0.95rem;">Internal Administration & Knowledge Platform</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.write("##### Sign in to your account")
            email = st.text_input("Email Address", placeholder="e.g. agent@enterprise.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Sign In", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.warning("Please supply both email and password credentials.")
                else:
                    try:
                        res = client.login(email, password)
                        st.session_state.token = res["access_token"]
                        st.session_state.current_user = client.get_me()
                        st.success("Access authorized.")
                        st.rerun()
                    except Exception as e:
                        st.error("Authentication failed. Please verify credentials.")

# ----------------- DASHBOARD PAGE -----------------
def render_dashboard_page():
    st.markdown('<div class="main-title">Operational Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">System performance, chunk load, and citation quality metrics</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    try:
        overview = client.get_overview()
        doc_status = client.get_document_status()
    except Exception as e:
        st.error(f"Failed to load analytics: {str(e)}")
        return

    # Overview Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Documents", overview.get("total_documents", 0))
    with col2:
        st.metric("Total Chunks", overview.get("total_chunks", 0))
    with col3:
        st.metric("Active Sessions", overview.get("total_chat_sessions", 0))
    with col4:
        st.metric("Total Feedbacks", overview.get("total_feedback", 0))

    st.write(" ")
    
    # Feedback Summary
    fcol1, fcol2, fcol3 = st.columns([1, 1, 2])
    with fcol1:
        st.write("##### 👍 Positive Ratings")
        st.subheader(overview.get("thumbs_up_count", 0))
    with fcol2:
        st.write("##### 👎 Low-Rated Count")
        st.subheader(overview.get("thumbs_down_count", 0))
    with fcol3:
        st.write("##### 📁 Document Pipeline Status")
        for k, v in doc_status.items():
            st.write(f"- **{k}**: {v}")

    st.write("---")

    # List recent questions & bad answers
    qcol, acol = st.columns(2)
    with qcol:
        st.write("##### 💬 Recent User Questions")
        try:
            questions = client.get_recent_questions(limit=5)
            if not questions:
                st.caption("No user queries recorded yet.")
            else:
                for q in questions:
                    st.info(f"**Q:** {q['content']} \n\n*Received at: {q['created_at'][:19]}*")
        except Exception as e:
            st.caption("Unable to load recent questions.")
            
    with acol:
        st.write("##### ⚠️ Low-Rated Assistant Answers")
        try:
            low_rated = client.get_low_rated_answers(limit=5)
            if not low_rated:
                st.caption("No negative feedback recorded.")
            else:
                for item in low_rated:
                    with st.expander(f"Answer: {item['answer'][:50]}...", expanded=False):
                        st.write(f"**Full Answer:** {item['answer']}")
                        st.write(f"**Feedback Score:** {item['score']} ({item['rating']})")
                        if item.get("comment"):
                            st.write(f"**Agent Comment:** \"{item['comment']}\"")
                        st.caption(f"Session: {item['session_id']} | Date: {item['created_at'][:19]}")
        except Exception as e:
            st.caption("Unable to load low-rated answers.")

# ----------------- DOCUMENTS PAGE -----------------
def render_documents_page():
    st.markdown('<div class="main-title">Document Repository</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Upload knowledge-base source documents and orchestrate index pipeline</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 1. Upload Form
    with st.expander("📤 Add New Document", expanded=True):
        uploaded_file = st.file_uploader("Select PDF, TXT or DOCX to upload (Max 25MB)", type=["pdf", "txt", "docx"])
        category = st.text_input("Optional Document Category (e.g. Refund Policy)")
        if st.button("Upload Document", use_container_width=True):
            if not uploaded_file:
                st.warning("Please select a valid file first.")
            else:
                try:
                    res = client.upload_document(
                        uploaded_file.name,
                        uploaded_file.read(),
                        uploaded_file.type,
                        category=category
                    )
                    st.success(f"Document uploaded successfully! ID: {res['id']}")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload failed: {str(e)}")

    st.write(" ")

    # 2. List & Orchestrate
    st.write("##### Knowledge Library Documents")
    try:
        docs_data = client.list_documents(page=1, size=50)
        docs = docs_data.get("items", [])
    except Exception as e:
        st.error(f"Failed to load documents list: {str(e)}")
        return

    if not docs:
        st.info("No documents uploaded yet.")
        return

    for doc in docs:
        status_color = "badge-completed" if doc["status"] == "Completed" else ("badge-failed" if doc["status"] == "Failed" else "badge-processing")
        
        with st.container():
            st.markdown(f"""
            <div style="background-color: #FAFAFA; border: 1px solid #E5E7EB; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{doc['filename']}</strong> <span class="badge {status_color}">{doc['status'].upper()}</span>
                        <br/>
                        <span style="font-size: 0.8rem; color: #6B7280;">Category: {doc.get('category') or 'None'} | Size: {doc['file_size']} bytes</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action Buttons under the card
            cols = st.columns(4)
            with cols[0]:
                if st.button("1️⃣ Extract Text", key=f"ext_{doc['id']}", use_container_width=True):
                    with st.spinner("Extracting..."):
                        try:
                            client.run_extraction(doc["id"])
                            st.success("Extraction complete.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Extraction failed: {str(e)}")
            with cols[1]:
                if st.button("2️⃣ Parse Chunks", key=f"chk_{doc['id']}", use_container_width=True):
                    with st.spinner("Chunking..."):
                        try:
                            client.run_chunking(doc["id"])
                            st.success("Semantic chunking complete.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Chunking failed: {str(e)}")
            with cols[2]:
                if st.button("3️⃣ Embed Chunks", key=f"emb_{doc['id']}", use_container_width=True):
                    with st.spinner("Embedding..."):
                        try:
                            client.run_embeddings(doc["id"])
                            st.success("Embedding generation complete.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Embedding failed: {str(e)}")
            with cols[3]:
                if st.button("4️⃣ Index Vectors", key=f"idx_{doc['id']}", use_container_width=True):
                    with st.spinner("Indexing..."):
                        try:
                            client.run_indexing(doc["id"])
                            st.success("Vector indexing complete.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Indexing failed: {str(e)}")

# ----------------- CHAT PAGE -----------------
def render_chat_page():
    st.markdown('<div class="main-title">Grounded AI Chat Support</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Ask support questions and review citations, sources, and verification stats</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Load sessions
    try:
        sessions = client.list_chat_sessions()
    except Exception as e:
        st.error(f"Failed to load sessions: {str(e)}")
        return

    # Session Selector
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        if sessions:
            session_options = {s["session_id"]: f"Session {s['session_id'][:8]} ({s['created_at'][:19]})" for s in sessions}
            # Fallback to first if not set
            if st.session_state.current_session_id not in session_options:
                st.session_state.current_session_id = list(session_options.keys())[0]
                
            selected_sid = st.selectbox(
                "Active Conversation Session", 
                options=list(session_options.keys()), 
                format_func=lambda x: session_options[x]
            )
            st.session_state.current_session_id = selected_sid
        else:
            st.info("No active chat sessions. Please create a new one.")
            st.session_state.current_session_id = None
    with sc2:
        st.write(" ") # Padding alignment
        if st.button("🆕 New Session", use_container_width=True):
            try:
                new_sess = client.create_chat_session()
                st.session_state.current_session_id = new_sess["session_id"]
                st.success("Session created.")
                st.rerun()
            except Exception as e:
                st.error(f"Create failed: {str(e)}")

    if not st.session_state.current_session_id:
        return

    # Message Area
    try:
        sess_detail = client.get_chat_session(st.session_state.current_session_id)
        messages = sess_detail.get("messages", [])
    except Exception as e:
        st.error(f"Failed to load session history: {str(e)}")
        return

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
            if msg["role"] == "assistant":
                # Display Citations if present
                if msg.get("citations"):
                    with st.expander("📚 Citations & Grounding Sources"):
                        for idx, src in enumerate(msg["citations"]):
                            st.markdown(f"**[{src['source_label']}]** {src['document_name']} (Page {src.get('page_number') or 1}) — Score: `{src['similarity_score']:.4f}`")
                            st.caption(f"\"{src['text_preview']}\"")
                
                # Display Verification
                if msg.get("verification"):
                    ver = msg["verification"]
                    status_lbl = ver["verification_status"].upper()
                    status_color = "green" if ver["verification_status"] == "verified" else "orange"
                    st.markdown(f"🛡️ **Verification:** :{status_color}[{status_lbl}] | Confidence: **{ver['confidence']*100:.1f}%**")
                    st.caption(f"Reasoning: {ver['reason']}")

                # Feedback widget
                with st.expander("💬 Submit Support Feedback", expanded=False):
                    f_rating = st.radio("Rate response:", ["Select", "👍 Useful", "👎 Needs Improvement"], key=f"r_{msg['id']}")
                    f_comment = st.text_input("Comment", placeholder="What was good/bad about this?", key=f"c_{msg['id']}")
                    if st.button("Submit Feedback", key=f"btn_{msg['id']}", use_container_width=True):
                        if f_rating == "Select":
                            st.warning("Please choose a rating.")
                        else:
                            r_val = "thumbs_up" if "Useful" in f_rating else "thumbs_down"
                            try:
                                client.submit_feedback(msg["id"], r_val, f_comment)
                                st.success("Feedback recorded successfully.")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Failed to record feedback: {str(ex)}")

    # Input Box
    query = st.chat_input("Enter customer support question...")
    if query:
        with st.chat_message("user"):
            st.write(query)
        with st.spinner("Retrieving facts and generating grounded answer..."):
            try:
                client.ask_session_question(st.session_state.current_session_id, query)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate answer: {str(e)}")

# ----------------- MAIN NAVIGATION -----------------
def main():
    if not st.session_state.token:
        render_login_page()
        return

    # Check health and user detail
    is_online = client.check_health()
    u = st.session_state.current_user or {}

    # Sidebar Header
    st.sidebar.markdown(f"""
    <div style="background-color: #F1F5F9; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
        <strong>🧑 {u.get('first_name', '')} {u.get('last_name', '')}</strong>
        <br/>
        <span style="font-size: 0.8rem; color: #666;">Role: {u.get('role', '')}</span>
        <br/>
        <span style="font-size: 0.8rem; color: #666;">Org ID: {u.get('organization_id', '')[:8]}...</span>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar Navigation Menu
    menu = ["📊 Dashboard", "📁 Documents", "💬 Chat Interface"]
    choice = st.sidebar.radio("Navigation", menu)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### System Telemetry")
    status_indicator = "🟢 Connected" if is_online else "🔴 Backend Offline"
    st.sidebar.write(f"Backend Link: **{status_indicator}**")
    
    st.sidebar.write(" ")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.token = None
        st.session_state.current_user = None
        st.session_state.current_session_id = None
        client.set_token(None)
        st.rerun()

    # Routing choice to pages
    if "Dashboard" in choice:
        render_dashboard_page()
    elif "Documents" in choice:
        render_documents_page()
    elif "Chat" in choice:
        render_chat_page()

if __name__ == "__main__":
    main()

import streamlit as st
import os
import time
import requests
from api_client import APIClient

# Page configuration
st.set_page_config(
    page_title="Enterprise AI Support Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom CSS for premium enterprise styling
st.markdown("""
<style>
    /* Global Font & Brand Theme */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #1E293B;
    }
    
    /* Layout styling */
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.04rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        font-weight: 500;
        margin-bottom: 1.5rem;
    }
    .divider {
        margin: 1rem 0 1.5rem 0;
        border-bottom: 1px solid #E2E8F0;
    }
    
    /* Premium Metric Cards */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 1.25rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    
    /* Status Badges */
    .badge {
        padding: 0.3rem 0.6rem;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.7rem;
        display: inline-block;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-new {
        background-color: #EFF6FF;
        color: #1D4ED8;
    }
    .badge-extracted {
        background-color: #F5F3FF;
        color: #6D28D9;
    }
    .badge-chunked {
        background-color: #ECFDF5;
        color: #047857;
    }
    .badge-embedded {
        background-color: #FFFBEB;
        color: #B45309;
    }
    .badge-completed {
        background-color: #F0FDF4;
        color: #166534;
        border: 1px solid #BBF7D0;
    }
    .badge-failed {
        background-color: #FEF2F2;
        color: #991B1B;
        border: 1px solid #FCA5A5;
    }
    
    /* Document Container Cards */
    .doc-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }
    
    /* Chat Answer styling */
    .chat-bubble-assistant {
        background-color: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 1rem;
        border-radius: 0 12px 12px 12px;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
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

# Helper function to set sticky feedback alerts
def set_doc_feedback(doc_id, status, message):
    st.session_state[f"feedback_{doc_id}"] = (status, message)

# Helper function to render and clear sticky feedback alerts
def render_doc_feedback(doc_id):
    key = f"feedback_{doc_id}"
    if key in st.session_state:
        status, msg = st.session_state[key]
        if status == "success":
            st.success(msg)
        else:
            st.error(msg)
        del st.session_state[key]

# Helper function to get correct badge class
def get_status_badge(status):
    status_lower = status.lower()
    if status_lower == "new":
        return "badge-new"
    elif status_lower == "extracted":
        return "badge-extracted"
    elif status_lower == "chunked":
        return "badge-chunked"
    elif status_lower == "embedded":
        return "badge-embedded"
    elif status_lower == "completed":
        return "badge-completed"
    else:
        return "badge-failed"

# ----------------- LOGIN PAGE -----------------
def render_login_page():
    _, col, _ = st.columns([1, 1.8, 1])
    with col:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 3rem; border-radius: 16px; text-align: center; color: white; margin-top: 4rem; margin-bottom: 2rem; box-shadow: 0 10px 25px rgba(30, 58, 138, 0.15);">
            <h1 style="margin: 0; font-weight: 800; font-size: 2.2rem; letter-spacing: -0.05rem;">Enterprise RAG Support</h1>
            <p style="margin: 0.75rem 0 0 0; opacity: 0.9; font-size: 1rem; font-weight: 400;">Grounded AI knowledge-base and customer support console.</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.write("### Sign in to Platform")
            email = st.text_input("Work Email Address", placeholder="e.g. admin@enterprise.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Authenticate Access", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.warning("⚠️ Work email and password fields are required.")
                else:
                    try:
                        res = client.login(email, password)
                        st.session_state.token = res["access_token"]
                        st.session_state.current_user = client.get_me()
                        st.success("✅ Authentication successful. Loading console...")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error("❌ Authentication failed. Please verify your email and password.")

# ----------------- DASHBOARD PAGE -----------------
def render_dashboard_page():
    st.markdown('<div class="main-title">Platform Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">System performance, chunk metrics, and grounding quality signals</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    try:
        overview = client.get_overview()
        doc_status = client.get_document_status()
    except Exception as e:
        st.error(f"❌ Failed to load telemetry data: {str(e)}")
        return

    # Check for empty state
    total_docs = overview.get("total_documents", 0)
    total_sessions = overview.get("total_chat_sessions", 0)
    total_feedback = overview.get("total_feedback", 0)
    
    if total_docs == 0 and total_sessions == 0 and total_feedback == 0:
        st.info("ℹ️ **No operational analytics available yet.** Upload files in the '📁 Documents' tab and start conversations in the '💬 Chat Interface' to generate dashboard analytics.")
        return

    # Overview Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <span style="font-size: 0.85rem; color: #64748B; font-weight: 600; text-transform: uppercase;">Total Docs</span>
            <h2 style="margin: 0.25rem 0 0 0; font-size: 2rem; font-weight: 800; color: #1E3A8A;">{total_docs}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        completed_docs = doc_status.get("Completed", 0)
        st.markdown(f"""
        <div class="metric-card">
            <span style="font-size: 0.85rem; color: #64748B; font-weight: 600; text-transform: uppercase;">Processed Docs</span>
            <h2 style="margin: 0.25rem 0 0 0; font-size: 2rem; font-weight: 800; color: #166534;">{completed_docs}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        failed_docs = doc_status.get("Failed", 0)
        st.markdown(f"""
        <div class="metric-card">
            <span style="font-size: 0.85rem; color: #64748B; font-weight: 600; text-transform: uppercase;">Failed Docs</span>
            <h2 style="margin: 0.25rem 0 0 0; font-size: 2rem; font-weight: 800; color: #991B1B;">{failed_docs}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <span style="font-size: 0.85rem; color: #64748B; font-weight: 600; text-transform: uppercase;">Chat Sessions</span>
            <h2 style="margin: 0.25rem 0 0 0; font-size: 2rem; font-weight: 800; color: #3B82F6;">{total_sessions}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <span style="font-size: 0.85rem; color: #64748B; font-weight: 600; text-transform: uppercase;">Total Feedbacks</span>
            <h2 style="margin: 0.25rem 0 0 0; font-size: 2rem; font-weight: 800; color: #D97706;">{total_feedback}</h2>
        </div>
        """, unsafe_allow_html=True)

    st.write(" ")
    st.write(" ")
    
    # Feedback Summary
    fcol1, fcol2, fcol3 = st.columns([1, 1, 2])
    with fcol1:
        st.write("##### 👍 Positive Ratings")
        st.markdown(f"### {overview.get('thumbs_up_count', 0)}")
    with fcol2:
        st.write("##### 👎 Low-Rated Answers")
        st.markdown(f"### {overview.get('thumbs_down_count', 0)}")
    with fcol3:
        st.write("##### 📁 Pipeline Phase Breakdown")
        for k, v in doc_status.items():
            st.write(f"- **{k}**: {v} documents")

    st.write("---")

    # List recent questions & bad answers
    qcol, acol = st.columns(2)
    with qcol:
        st.write("##### 💬 Recent Queries")
        try:
            questions = client.get_recent_questions(limit=5)
            if not questions:
                st.info("No queries recorded yet.")
            else:
                for q in questions:
                    st.info(f"**Q:** {q['content']} \n\n*Received at: {q['created_at'][:19]}*")
        except Exception:
            st.caption("Unable to load recent queries.")
            
    with acol:
        st.write("##### ⚠️ Negative Feedbacks Log")
        try:
            low_rated = client.get_low_rated_answers(limit=5)
            if not low_rated:
                st.info("No negative feedbacks logged yet.")
            else:
                for item in low_rated:
                    with st.expander(f"Answer: {item['answer'][:50]}...", expanded=False):
                        st.write(f"**Full Answer:** {item['answer']}")
                        st.write(f"**Feedback Score:** {item['score']} ({item['rating']})")
                        if item.get("comment"):
                            st.write(f"**Agent Comment:** \"{item['comment']}\"")
                        st.caption(f"Session: {item['session_id']} | Date: {item['created_at'][:19]}")
        except Exception:
            st.caption("Unable to load low-rated answers.")

# ----------------- DOCUMENTS PAGE -----------------
def render_documents_page():
    st.markdown('<div class="main-title">Document Repository</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Upload source documents and orchestrate the vector ingestion pipeline</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 1. Upload Form
    with st.expander("📤 Upload New Document", expanded=True):
        uploaded_file = st.file_uploader("Select PDF, TXT or DOCX to upload (Max 25MB)", type=["pdf", "txt", "docx"])
        category = st.text_input("Document Category (e.g. Product Warranty, Refund Policy)")
        if st.button("Upload Document to Library", use_container_width=True):
            if not uploaded_file:
                st.warning("⚠️ Please select a valid file first.")
            else:
                with st.spinner("Uploading and registering document..."):
                    try:
                        res = client.upload_document(
                            uploaded_file.name,
                            uploaded_file.read(),
                            uploaded_file.type,
                            category=category
                        )
                        st.success(f"✅ Uploaded successfully! ID: {res['id']}")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Upload failed: {str(e)}")

    st.write(" ")

    # 2. List & Ingestion Pipelines
    st.write("##### Ingestion Pipelines")
    try:
        docs_data = client.list_documents(page=1, size=50)
        docs = docs_data.get("items", [])
    except Exception as e:
        st.error(f"❌ Failed to load documents list: {str(e)}")
        return

    if not docs:
        st.info("📁 **No documents in repository.** Upload a source document above to start indexing knowledge bases.")
        return

    for doc in docs:
        badge_class = get_status_badge(doc["status"])
        file_ext = doc['filename'].split('.')[-1].upper() if '.' in doc['filename'] else 'TXT'
        upload_time = doc.get("created_at", "")[:19].replace("T", " ")
        
        with st.container():
            st.markdown(f"""
            <div style="background-color: #FCFDFE; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.25rem; margin-bottom: 0.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                    <div>
                        <span style="font-size: 0.75rem; background-color: #F1F5F9; color: #475569; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700; margin-right: 0.5rem;">{file_ext}</span>
                        <strong style="font-size: 1.05rem; color: #1E293B;">{doc['filename']}</strong>
                        <span style="margin-left: 0.75rem;" class="badge {badge_class}">{doc['status'].upper()}</span>
                        <br/>
                        <span style="font-size: 0.8rem; color: #64748B;">Category: <b>{doc.get('category') or 'General'}</b> | Size: {doc['file_size']} bytes | Uploaded: {upload_time}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show sticky feedback if any exists
            render_doc_feedback(doc["id"])
            
            # Action Buttons under the card
            cols = st.columns(4)
            with cols[0]:
                is_ext_disabled = doc["status"] in ["Extracted", "Chunked", "Embedded", "Completed"]
                if st.button("1️⃣ Extract Text", key=f"ext_{doc['id']}", use_container_width=True, disabled=is_ext_disabled):
                    with st.spinner("Extracting content..."):
                        try:
                            client.run_extraction(doc["id"])
                            set_doc_feedback(doc["id"], "success", "✅ Text extracted successfully. Next step: **2️⃣ Parse Chunks**.")
                            st.rerun()
                        except Exception as e:
                            set_doc_feedback(doc["id"], "error", f"❌ Extraction failed: {str(e)}")
                            st.rerun()
                            
            with cols[1]:
                is_chk_disabled = doc["status"] not in ["Extracted"]
                if st.button("2️⃣ Parse Chunks", key=f"chk_{doc['id']}", use_container_width=True, disabled=is_chk_disabled):
                    with st.spinner("Parsing text chunks..."):
                        try:
                            client.run_chunking(doc["id"])
                            set_doc_feedback(doc["id"], "success", "✅ Text chunks parsed successfully. Next step: **3️⃣ Generate Embeddings**.")
                            st.rerun()
                        except Exception as e:
                            set_doc_feedback(doc["id"], "error", f"❌ Chunking failed: {str(e)}")
                            st.rerun()
                            
            with cols[2]:
                is_emb_disabled = doc["status"] not in ["Chunked"]
                if st.button("3️⃣ Generate Embeddings", key=f"emb_{doc['id']}", use_container_width=True, disabled=is_emb_disabled):
                    with st.spinner("Generating embeddings..."):
                        try:
                            client.run_embeddings(doc["id"])
                            set_doc_feedback(doc["id"], "success", "✅ Embeddings generated successfully! Next step: **4️⃣ Index Vectors**.")
                            st.rerun()
                        except Exception as e:
                            set_doc_feedback(doc["id"], "error", f"❌ Embedding generation failed: {str(e)}")
                            st.rerun()
                            
            with cols[3]:
                is_idx_disabled = doc["status"] not in ["Embedded"]
                if st.button("4️⃣ Index Vectors", key=f"idx_{doc['id']}", use_container_width=True, disabled=is_idx_disabled):
                    with st.spinner("Syncing to vector database..."):
                        try:
                            client.run_indexing(doc["id"])
                            set_doc_feedback(doc["id"], "success", "✅ Vector indexing complete! The knowledge source is now fully active in chat grounding.")
                            st.rerun()
                        except Exception as e:
                            set_doc_feedback(doc["id"], "error", f"❌ Vector indexing failed: {str(e)}")
                            st.rerun()
            st.write(" ")

# ----------------- CHAT PAGE -----------------
def render_chat_page():
    st.markdown('<div class="main-title">Grounded Chat Support</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Test prompt grounding, retrieval, citations, and output verification</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Load sessions
    try:
        sessions = client.list_chat_sessions()
    except Exception as e:
        st.error(f"❌ Failed to load chat sessions: {str(e)}")
        return

    # Session Selector
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        if sessions:
            session_options = {s["session_id"]: f"Session {s['session_id'][:8]} (Created {s['created_at'][:10]} {s['created_at'][11:16]})" for s in sessions}
            if st.session_state.current_session_id not in session_options:
                st.session_state.current_session_id = list(session_options.keys())[0]
                
            selected_sid = st.selectbox(
                "Select Chat Conversation Session", 
                options=list(session_options.keys()), 
                format_func=lambda x: session_options[x]
            )
            st.session_state.current_session_id = selected_sid
        else:
            st.info("ℹ️ **No active chat sessions.** Click the button to the right to start a new support conversation.")
            st.session_state.current_session_id = None
    with sc2:
        st.write(" ") # Space alignment
        if st.button("🆕 New Chat Session", use_container_width=True):
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
        st.error(f"❌ Failed to load session messages: {str(e)}")
        return

    if not messages:
        st.info("💬 **This session is empty.** Enter a query in the chat input below to retrieve facts and generate grounded answers.")

    for msg in messages:
        role_label = "Agent" if msg["role"] == "user" else "Assistant"
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(f"**{msg['content']}**")
            else:
                st.markdown(f'<div class="chat-bubble-assistant">{msg["content"]}</div>', unsafe_allow_html=True)
                
                # Display Citations if present
                if msg.get("citations"):
                    with st.expander("📚 Grounded Sources & Citations", expanded=False):
                        for idx, src in enumerate(msg["citations"]):
                            st.markdown(f"**[{src['source_label']}]** {src['document_name']} (Page {src.get('page_number') or 1}) — Vector Score: `{src['similarity_score']:.4f}`")
                            st.caption(f"\"{src['text_preview']}\"")
                
                # Display Verification
                if msg.get("verification"):
                    ver = msg["verification"]
                    status_lbl = ver["verification_status"].upper()
                    status_color = "green" if ver["verification_status"] == "verified" else "orange"
                    st.markdown(f"🛡️ **Output Verification:** :{status_color}[{status_lbl}] | Confidence: **{ver['confidence']*100:.1f}%**")
                    st.caption(f"*Reasoning:* {ver['reason']}")

                # Feedback widget
                feedback_submit_key = f"feedback_success_{msg['id']}"
                if feedback_submit_key in st.session_state:
                    st.success(st.session_state[feedback_submit_key])
                else:
                    with st.expander("💬 Rate this Response", expanded=False):
                        f_rating = st.radio("Rate this answer:", ["Select", "👍 Grounded & Useful", "👎 Hallucinated / Out of Context"], key=f"r_{msg['id']}")
                        f_comment = st.text_input("Comment", placeholder="Optional feedback details...", key=f"c_{msg['id']}")
                        if st.button("Submit Feedback", key=f"btn_{msg['id']}", use_container_width=True):
                            if f_rating == "Select":
                                st.warning("⚠️ Please choose a rating first.")
                            else:
                                r_val = "thumbs_up" if "Useful" in f_rating else "thumbs_down"
                                try:
                                    client.submit_feedback(msg["id"], r_val, f_comment)
                                    st.session_state[feedback_submit_key] = "✅ Thanks! Your rating and comments have been recorded."
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"Failed to submit feedback: {str(ex)}")

    # Input Box
    query = st.chat_input("Ask a question about the uploaded customer policies...")
    if query:
        with st.chat_message("user"):
            st.markdown(f"**{query}**")
        with st.spinner("Searching vector indexes and generating grounded response..."):
            try:
                client.ask_session_question(st.session_state.current_session_id, query)
                st.rerun()
            except requests.exceptions.HTTPError as http_err:
                try:
                    error_detail = http_err.response.json().get("detail", "")
                except Exception:
                    error_detail = http_err.response.text
                
                # Check for rate limit or quota exceeded errors
                if "quota" in error_detail.lower() or "429" in error_detail.lower() or "limit" in error_detail.lower():
                    st.warning("⚠️ **Gemini quota is currently exhausted.** Retrieval and indexing are working, but answer generation is temporarily blocked by the provider. Please try again later.")
                else:
                    st.error(f"❌ Grounded generation failed: {error_detail}")
            except Exception as e:
                st.error(f"❌ Failed to request answer: {str(e)}")

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
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
        <span style="font-size: 0.8rem; color: #64748B; font-weight: 700; text-transform: uppercase;">Active Session</span>
        <h4 style="margin: 0.25rem 0 0 0; font-weight: 800; color: #1E293B;">{u.get('first_name', '')} {u.get('last_name', '')}</h4>
        <span style="font-size: 0.8rem; color: #475569;">Role: <b>{u.get('role', '')}</b></span>
        <br/>
        <span style="font-size: 0.75rem; color: #94A3B8;">Org: {u.get('organization_id', '')[:8]}...</span>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar Navigation Menu
    menu = ["📊 Dashboard View", "📁 Documents Manager", "💬 Chat Console"]
    choice = st.sidebar.radio("Console Navigation", menu)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Telemetry")
    status_indicator = "🟢 Online" if is_online else "🔴 Offline"
    st.sidebar.write(f"Backend Link: **{status_indicator}**")
    
    st.sidebar.write(" ")
    if st.sidebar.button("Sign Out of Platform", use_container_width=True):
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

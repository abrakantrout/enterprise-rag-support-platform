import streamlit as st

# Configure page settings for a clean, modern layout
st.set_page_config(
    page_title="Enterprise AI Knowledge Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom CSS for premium styling
st.markdown("""
<style>
    /* Styling headers */
    .main-header {
        font-family: 'Inter', sans-serif;
        color: #1A365D;
        font-size: 3.2rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        letter-spacing: -0.05rem;
    }
    .sub-header {
        font-family: 'Inter', sans-serif;
        color: #3182CE;
        font-size: 1.6rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
    }
    .card-panel {
        background-color: #F7FAFC;
        padding: 2.0rem;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .badge-status {
        background-color: #C6F6D5;
        color: #22543D;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .divider-line {
        margin-top: 2rem;
        margin-bottom: 2rem;
        border-bottom: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# Main Application Layout
st.markdown('<div class="main-header">Enterprise AI Knowledge Platform</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Intelligent Customer Support (RAG)</div>', unsafe_allow_html=True)
st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)

# Welcome Container Card
st.markdown(
    """
    <div class="card-panel">
        <h3>👋 Welcome to the Platform</h3>
        <p>The enterprise-grade architecture foundation is fully initialized and operational.</p>
        <p>This layout acts as the user interface shell that will coordinate customer chat interfaces, 
        document uploads libraries, and analytics dashboards in subsequent sprint deliveries.</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Sidebar Management Console Placeholder
st.sidebar.title("Management Console")
st.sidebar.markdown("---")
st.sidebar.markdown("### System Telemetry")
st.sidebar.write("App Status: 🟢 **Active**")
st.sidebar.write("Sprint: 📦 **Sprint 1 (Foundation)**")
st.sidebar.markdown("---")
st.sidebar.info("💡 **Developer Notice:** Backend services, relational tables, and ChromaDB vector connectors are set up and awaiting logic in Sprint 2.")

"""
Memory monitoring utilities for tracking memory usage and potential leaks
"""

import os
import gc
import tracemalloc
import streamlit as st

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil not available - install for memory monitoring")

# Start tracemalloc on module load
if not tracemalloc.is_tracing():
    tracemalloc.start()

def get_rss_mb():
    """Get resident set size in MB"""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        return round(psutil.Process(os.getpid()).memory_info().rss / (1024*1024), 1)
    except:
        return None

@st.cache_data(ttl=15, max_entries=1)
def get_memory_snapshot():
    """Get memory snapshot with top allocators"""
    rss = get_rss_mb()

    if not tracemalloc.is_tracing():
        return rss, []

    try:
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('filename')[:10]

        allocators = []
        for stat in top_stats:
            filename = str(stat.traceback[0].filename) if stat.traceback else "unknown"
            size_mb = stat.size / (1024*1024)
            allocators.append((filename, size_mb))

        return rss, allocators
    except:
        return rss, []

def render_memory_panel():
    """Render memory monitoring panel in sidebar"""
    if not PSUTIL_AVAILABLE:
        return

    st.sidebar.divider()
    st.sidebar.subheader("🔧 System")

    rss, top_allocators = get_memory_snapshot()

    if rss is not None:
        st.sidebar.metric("Process RSS", f"{rss} MB")

    # Force GC button
    if st.sidebar.button("Force GC", help="Force garbage collection"):
        gc.collect()
        st.sidebar.success(f"GC complete! RSS: {get_rss_mb()} MB")

    # Clear caches button
    if st.sidebar.button("Clear Caches", help="Clear all Streamlit caches"):
        st.cache_data.clear()
        st.sidebar.success("Caches cleared!")

    # Show top allocators in expander
    if top_allocators:
        with st.sidebar.expander("Top Memory Allocators"):
            for filename, size_mb in top_allocators:
                # Show just the filename, not full path
                short_name = filename.split('/')[-1] if '/' in filename else filename
                st.write(f"• {short_name}: {size_mb:.2f} MB")

import streamlit as st
from google import genai
import os
from google_docs_integration import create_google_doc
from datetime import datetime

# Initialize Gemini client
@st.cache_resource
def get_client():
    # Try to get API key from Streamlit secrets (for deployment)
    if hasattr(st, 'secrets') and "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        # Fall back to environment variable (for local development)
        api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        st.error("GEMINI_API_KEY not found. Please configure it in Streamlit secrets or environment variables.")
        st.stop()
    
    return genai.Client(api_key=api_key)

def generate_profile(question_answers):
    """Generate mirror profile from question answers"""
    
    client = get_client()
    prompt_dir = "./prompts/"
    
    # Step 1: Generate master extraction
    st.info("🔄 Generating master extraction...")
    progress_bar = st.progress(0)
    
    try:
        prompt1 = open(f"{prompt_dir}/p1.txt", "r", encoding="utf-8").read().strip()
    except FileNotFoundError:
        st.error(f"Prompt file not found: {prompt_dir}/p1.txt")
        st.info("Make sure your prompts directory is in the repository")
        return None, None
    
    prompt1 = prompt1.replace("<<question_answers>>", question_answers)
    
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=prompt1,
    )
    master_extraction = response.text
    
    if len(master_extraction) < 20:
        st.error("Master extraction looks empty or too short")
        return None, None
    
    progress_bar.progress(10)
    
    # Read common files
    try:
        common_includes = open(f"{prompt_dir}/common_includes.txt", "r", encoding="utf-8").read().strip()
        common_instructions = open(f"{prompt_dir}/common_instructions.txt", "r", encoding="utf-8").read().strip()
    except FileNotFoundError as e:
        st.error(f"Required prompt file not found: {e}")
        return None, None
    
    # Step 2: Generate sections
    final_mirror_profile = ""
    
    for i in range(2, 16):
        st.info(f"🔄 Generating section {i-1}...")
        progress = 10 + int((i-1) / 14 * 80)
        progress_bar.progress(progress)
        
        prompt_path = f"{prompt_dir}/p{i}.txt"
        if not os.path.exists(prompt_path):
            st.warning(f"Prompt file not found: {prompt_path}, skipping...")
            continue
            
        prompt = open(prompt_path, "r", encoding="utf-8").read().strip()
        prompt = prompt.replace("<<master_extraction>>", master_extraction)
        prompt = prompt.replace("<<question_answers>>", question_answers)
        prompt = prompt.replace("<<common_includes>>", common_includes)
        prompt = prompt.replace("<<common_instructions>>", common_instructions)
        prompt = prompt.replace("<<section_number>>", str(i-1))
        
        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=prompt,
        )
        section_mirror_profile = response.text + "\n\n"
        
        if len(section_mirror_profile) < 20:
            st.warning(f"Section {i-1} looks empty or too short")
            continue
        
        final_mirror_profile += section_mirror_profile
    
    progress_bar.progress(90)
    
    # Step 3: Create Google Doc
    st.info("📄 Creating Google Doc...")
    doc_title = f"mirror_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    response = create_google_doc(doc_title, final_mirror_profile)
    
    progress_bar.progress(100)
    
    return final_mirror_profile, response

def main():
    st.set_page_config(
        page_title="Mirror Profile Generator",
        page_icon="📝",
        layout="wide"
    )
    
    st.title("📝 Mirror Profile Generator")
    st.markdown("Generate comprehensive mirror profiles from question-answer data")
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📥 Input")
        
        question_answers = st.text_area(
            "Paste your question-answers here:",
            height=400,
            placeholder="Enter the question-answer text..."
        )
        
        # Validation
        if question_answers and len(question_answers) >= 20:
            st.success(f"✅ Ready ({len(question_answers)} characters)")
        elif question_answers:
            st.error("❌ Too short (minimum 20 characters)")
        
        # Generate button
        generate_btn = st.button(
            "🚀 Generate Mirror Profile",
            type="primary",
            use_container_width=True,
            disabled=not question_answers or len(question_answers) < 20
        )
    
    with col2:
        st.subheader("📄 Output")
        
        if generate_btn:
            with st.spinner("Generating profile..."):
                try:
                    final_profile, doc_response = generate_profile(question_answers)
                    
                    if final_profile:
                        st.success("✅ Profile generated successfully!")
                        
                        # Show Google Doc link
                        if doc_response and doc_response.get('success'):
                            st.markdown(f"### 📝 [Open Google Doc]({doc_response['document_url']})")
                        else:
                            st.error(f"Google Doc creation failed: {doc_response.get('message', 'Unknown error')}")
                        
                        # Show preview
                        with st.expander("📋 Preview Profile", expanded=False):
                            st.text_area("Generated Profile:", final_profile, height=400, disabled=True)
                        
                        # Download button
                        st.download_button(
                            "📥 Download as TXT",
                            final_profile,
                            file_name=f"mirror_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                        
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
        else:
            st.info("👈 Enter question-answers and click 'Generate' to start")

if __name__ == "__main__":
    main()
    
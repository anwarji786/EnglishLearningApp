import streamlit as st
import json
import os
import random
from pathlib import Path

# Clear session state
for key in list(st.session_state.keys()):
    if key not in ['stories_loaded', 'current_story_index']:
        del st.session_state[key]

st.set_page_config(page_title="Language Learner", layout="wide")

# Load all stories from JSON files
@st.cache_data
def load_all_stories():
    stories = []
    json_files = [f for f in os.listdir(".") if f.endswith('.json') and f not in ['user_data.json', 'requirements.txt']]
    
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'content' in data:
                # Extract words from content
                words = []
                for item in data['content']:
                    if isinstance(item, dict) and 'english' in item:
                        words.append({
                            'english': item['english'],
                            'hindi': item.get('hindi', ''),
                            'phonetic': item.get('phonetic', ''),
                            'example': f"This is {item['english']}."
                        })
                
                if words:
                    stories.append({
                        'filename': json_file,
                        'title': data.get('title', json_file.replace('.json', '')),
                        'hindi_title': data.get('hindi_title', ''),
                        'level': data.get('level', 'Beginner'),
                        'words': words
                    })
                    
        except Exception as e:
            st.error(f"Error loading {json_file}: {e}")
    
    return stories

# Load stories
stories = load_all_stories()

# Initialize session state
if 'stories_loaded' not in st.session_state:
    st.session_state.stories_loaded = True
    st.session_state.current_story_index = 0
    st.session_state.current_word_index = 0
    st.session_state.show_meaning = False

# Title
st.title("📚 Language Learner")

# Sidebar for story selection
with st.sidebar:
    st.header("Select a Story")
    
    if stories:
        story_options = [f"{s['title']} ({len(s['words'])} words)" for s in stories]
        selected_story = st.selectbox(
            "Choose a story:",
            range(len(stories)),
            format_func=lambda i: story_options[i],
            key="story_selector"
        )
        
        # Update current story index if changed
        if selected_story != st.session_state.current_story_index:
            st.session_state.current_story_index = selected_story
            st.session_state.current_word_index = 0
            st.session_state.show_meaning = False
            st.rerun()
        
        # Show story info
        current_story_data = stories[st.session_state.current_story_index]
        st.subheader(current_story_data['title'])
        if current_story_data['hindi_title']:
            st.write(f"Hindi: {current_story_data['hindi_title']}")
        st.write(f"Level: {current_story_data['level']}")
        st.write(f"Words: {len(current_story_data['words'])}")
        
        st.markdown("---")
        st.subheader("Words in this story:")
        for i, word in enumerate(current_story_data['words']):
            if i == st.session_state.current_word_index:
                st.markdown(f"**→ {i+1}. {word['english']}**")
            else:
                st.write(f"{i+1}. {word['english']}")
    
    else:
        st.warning("No stories found!")

# Main content area
if stories:
    current_story = stories[st.session_state.current_story_index]
    current_words = current_story['words']
    
    # Check bounds
    if st.session_state.current_word_index >= len(current_words):
        st.session_state.current_word_index = 0
    
    current_word = current_words[st.session_state.current_word_index]
    
    # Display current story title
    st.subheader(f"📖 {current_story['title']}")
    if current_story['hindi_title']:
        st.caption(f"हिंदी: {current_story['hindi_title']}")
    
    # Navigation
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        if st.button("⬅️ Previous", 
                    disabled=(st.session_state.current_word_index == 0),
                    key="prev_button",
                    use_container_width=True):
            st.session_state.current_word_index -= 1
            st.session_state.show_meaning = False
            st.rerun()
    
    with col3:
        if st.button("Next ➡️", 
                    disabled=(st.session_state.current_word_index == len(current_words)-1),
                    key="next_button", 
                    use_container_width=True):
            st.session_state.current_word_index += 1
            st.session_state.show_meaning = False
            st.rerun()
    
    with col2:
        progress = (st.session_state.current_word_index + 1) / len(current_words)
        st.progress(progress)
        st.caption(f"Word {st.session_state.current_word_index + 1} of {len(current_words)}")
    
    # Display current word
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 50px;
        border-radius: 25px;
        text-align: center;
        margin: 30px 0;
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    ">
        <div style="font-size: 6rem; margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
            ✨
        </div>
        <div style="font-size: 5rem; font-weight: bold; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
            {current_word['english']}
        </div>
        <div style="font-size: 1.5rem; opacity: 0.9;">
            {current_word.get('phonetic', f"/{current_word['english'].lower()}/")}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show/Hide meaning button
    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        if st.button(
            "🔍 Show Meaning" if not st.session_state.show_meaning else "🙈 Hide Meaning",
            type="secondary",
            use_container_width=True,
            key="meaning_button"
        ):
            st.session_state.show_meaning = not st.session_state.show_meaning
            st.rerun()
    
    # Audio placeholder
    with col_btn2:
        if st.button("🔊 Play Audio", use_container_width=True, key="audio_button"):
            st.info(f"Audio for: {current_word['english']}")
    
    # Show meaning if toggled
    if st.session_state.show_meaning:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 40px;
            border-radius: 20px;
            margin: 20px 0;
            color: white;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        ">
            <div style="font-size: 4rem; font-weight: bold; margin-bottom: 20px;">
                {current_word['hindi']}
            </div>
            <div style="font-size: 1.3rem; font-style: italic; margin-bottom: 15px;">
                {current_word.get('example', f"This is {current_word['english']}.")}
            </div>
            <div style="
                background: rgba(255,255,255,0.2);
                padding: 15px;
                border-radius: 10px;
                backdrop-filter: blur(10px);
            ">
                <strong>💡 Tip:</strong> Practice saying "{current_word['english']}" and "{current_word['hindi']}" together
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Quick navigation
    st.markdown("---")
    st.subheader("Quick Navigation")
    
    # Create buttons for quick word selection
    cols = st.columns(5)
    for i in range(min(10, len(current_words))):
        with cols[i % 5]:
            if st.button(
                f"{i+1}. {current_words[i]['english']}",
                key=f"quick_{i}",
                use_container_width=True,
                type="primary" if i == st.session_state.current_word_index else "secondary"
            ):
                st.session_state.current_word_index = i
                st.session_state.show_meaning = False
                st.rerun()
    
else:
    st.error("No stories found! Please make sure you have JSON files in the correct format.")
    st.info("""
    **Expected JSON format:**
    ```json
    {
        "title": "Story Title",
        "hindi_title": "हिंदी शीर्षक",
        "level": "Beginner",
        "content": [
            {"english": "Hello", "hindi": "नमस्ते", "phonetic": "/həˈloʊ/"},
            {"english": "Goodbye", "hindi": "अलविदा", "phonetic": "/ˌɡʊdˈbaɪ/"}
        ]
    }
    ```
    """)

# Reset button
if st.sidebar.button("🔄 Reset to First Word", use_container_width=True):
    st.session_state.current_word_index = 0
    st.session_state.show_meaning = False
    st.rerun()

import streamlit as st
import json
import os
import random
from pathlib import Path
from gtts import gTTS
import io
import base64

# Clear all session state first
for key in list(st.session_state.keys()):
    del st.session_state[key]

# Simple Word class
class Word:
    def __init__(self, english, hindi, emoji="📝"):
        self.english = english
        self.hindi = hindi
        self.emoji = emoji

# Load stories function
def load_stories():
    """Super simple story loader"""
    stories = []
    
    # Always use test data first
    test_words = [
        Word("Hello", "नमस्ते", "👋"),
        Word("Goodbye", "अलविदा", "👋"),
        Word("Thank you", "धन्यवाद", "🙏"),
        Word("Please", "कृपया", "🙏"),
        Word("Water", "पानी", "💧"),
        Word("Food", "भोजन", "🍕"),
        Word("Friend", "दोस्त", "👫"),
        Word("House", "घर", "🏠"),
        Word("Book", "किताब", "📚"),
        Word("School", "स्कूल", "🏫")
    ]
    
    # Create a simple test story
    stories.append({
        "title": "Basic English Words",
        "words": test_words
    })
    
    return stories

# Main app
def main():
    st.set_page_config(page_title="Simple Language App", layout="wide")
    
    st.title("📚 Simple Language Learner")
    
    # Load stories
    stories = load_stories()
    
    # Show current story
    current_story = stories[0]
    words = current_story["words"]
    
    # Initialize session
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0
    if 'show_meaning' not in st.session_state:
        st.session_state.show_meaning = False
    
    # Get current word
    idx = st.session_state.current_index
    if idx >= len(words):
        idx = 0
        st.session_state.current_index = 0
    
    current_word = words[idx]
    
    # Navigation
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("⬅️ Previous", disabled=idx==0):
            st.session_state.current_index -= 1
            st.session_state.show_meaning = False
            st.rerun()
    
    with col3:
        if st.button("Next ➡️", disabled=idx==len(words)-1):
            st.session_state.current_index += 1
            st.session_state.show_meaning = False
            st.rerun()
    
    with col2:
        st.progress((idx + 1) / len(words))
        st.caption(f"Word {idx + 1} of {len(words)}")
    
    # Display word
    st.markdown(f"""
    <div style="
        background: #f0f2f6;
        padding: 40px;
        border-radius: 20px;
        text-align: center;
        margin: 20px 0;
        border: 3px solid #4f46e5;
    ">
        <div style="font-size: 5rem; margin-bottom: 20px;">{current_word.emoji}</div>
        <div style="font-size: 4rem; font-weight: bold; color: #4f46e5;">
            {current_word.english}
        </div>
        <div style="font-size: 1.5rem; color: #666; margin-top: 10px;">
            Pronunciation: /{current_word.english.lower()}/
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show the actual word as text too (for debugging)
    st.write(f"**Debug:** Current word is '{current_word.english}'")
    
    # Audio
    try:
        tts = gTTS(text=current_word.english, lang='en', slow=True)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        b64_audio = base64.b64encode(audio_bytes.read()).decode()
        audio_html = f"""
        <div style="margin: 30px 0;">
            <audio controls style="width: 100%; height: 50px;">
                <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mpeg">
            </audio>
        </div>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    except:
        st.warning("Audio generation failed")
    
    # Show meaning button
    if st.button("Show Meaning", type="secondary", use_container_width=True):
        st.session_state.show_meaning = not st.session_state.show_meaning
        st.rerun()
    
    # Show meaning if toggled
    if st.session_state.show_meaning:
        st.markdown(f"""
        <div style="
            background: #e3f2fd;
            padding: 25px;
            border-radius: 15px;
            margin: 20px 0;
            text-align: center;
        ">
            <div style="font-size: 3.5rem; color: #0ea5e9; font-weight: bold;">
                {current_word.hindi}
            </div>
            <div style="margin-top: 15px; font-style: italic; font-size: 1.2rem;">
                Example: "This is {current_word.english.lower()}"
            </div>
            <div style="margin-top: 15px; background: white; padding: 15px; border-radius: 10px;">
                💡 <strong>Tip:</strong> Remember "{current_word.english}" as "{current_word.hindi}"
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Show all words in sidebar
    with st.sidebar:
        st.header("All Words")
        for i, word in enumerate(words):
            if i == idx:
                st.markdown(f"**→ {i+1}. {word.english}**")
            else:
                st.write(f"{i+1}. {word.english}")
        
        st.markdown("---")
        if st.button("Reset to first word"):
            st.session_state.current_index = 0
            st.session_state.show_meaning = False
            st.rerun()

if __name__ == "__main__":
    main()

import streamlit as st
import json
import time
import random
import uuid
from pathlib import Path
from gtts import gTTS
import io
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import hashlib
from datetime import datetime
import glob
import os
import base64

# ============================================================================
# CONFIGURATION & MODELS
# ============================================================================

@dataclass
class WordData:
    english: str
    hindi: str
    phonetic: str
    category: str
    difficulty: int
    example_sentence: str
    mnemonic: str
    image_hint: str
    mastery_level: float = 0.0
    last_reviewed: Optional[datetime] = None
    review_count: int = 0

@dataclass
class UserProfile:
    name: str = "Learner"
    dark_mode: bool = False

# ============================================================================
# STORAGE
# ============================================================================

class StorageManager:
    def __init__(self):
        self.data_dir = Path("learning_data")
        self.data_dir.mkdir(exist_ok=True)
    
    def save(self, profile: UserProfile, all_words: List[WordData]):
        data = {
            "profile": asdict(profile),
            "words": [asdict(w) for w in all_words],
        }
        with open(self.data_dir / "user_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def load(self):
        try:
            with open(self.data_dir / "user_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = UserProfile(**data["profile"])
            words = []
            for w in data["words"]:
                words.append(WordData(**w))
            return profile, words
        except:
            return UserProfile(), []

# ============================================================================
# AUDIO MANAGER
# ============================================================================

class AudioManager:
    def __init__(self):
        self.cache_dir = Path("audio_cache")
        self.cache_dir.mkdir(exist_ok=True)

    def get_audio_bytes(self, text: str, slow: bool = False):
        if not text: return None
        
        clean_text = text.strip()
        if not clean_text: return None

        hash_key = hashlib.md5(f"{clean_text}_{slow}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{hash_key}.mp3"

        if cache_file.exists():
            return cache_file.read_bytes()

        try:
            tts = gTTS(text=clean_text, lang="en", slow=slow)
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            audio_data = mp3_fp.read()
            cache_file.write_bytes(audio_data)
            return audio_data
        except Exception as e:
            return None

# ============================================================================
# STORY LOADER - ULTRA SIMPLE
# ============================================================================

def load_stories_from_files():
    """Very simple story loader"""
    stories = []
    
    # Create test data if no JSON files
    test_data = [
        {"english": "Hello", "hindi": "नमस्ते", "emoji": "👋"},
        {"english": "Goodbye", "hindi": "अलविदा", "emoji": "👋"},
        {"english": "Thank you", "hindi": "धन्यवाद", "emoji": "🙏"},
        {"english": "Please", "hindi": "कृपया", "emoji": "🙏"},
        {"english": "Sorry", "hindi": "माफ़ कीजिए", "emoji": "😔"},
        {"english": "Yes", "hindi": "हाँ", "emoji": "✅"},
        {"english": "No", "hindi": "नहीं", "emoji": "❌"},
        {"english": "Water", "hindi": "पानी", "emoji": "💧"},
        {"english": "Food", "hindi": "भोजन", "emoji": "🍕"},
        {"english": "Friend", "hindi": "दोस्त", "emoji": "👫"}
    ]
    
    # Try to load actual JSON files first
    json_files = [f for f in glob.glob("*.json") 
                  if os.path.basename(f) not in ["user_data.json", "requirements.txt"]]
    
    if json_files:
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                word_list = []
                
                # Handle different JSON structures
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict) and "content" in data:
                    items = data["content"]
                elif isinstance(data, dict) and "words" in data:
                    items = data["words"]
                else:
                    items = []
                
                for item in items:
                    if isinstance(item, dict):
                        # Get English word
                        english = ""
                        for key in ["english", "English", "word", "Word"]:
                            if key in item:
                                english = str(item[key])
                                break
                        
                        if english:
                            # Get Hindi
                            hindi = ""
                            for key in ["hindi", "Hindi", "translation"]:
                                if key in item:
                                    hindi = str(item[key])
                                    break
                            
                            if not hindi:
                                hindi = f"Translation for {english}"
                            
                            # Create word
                            word = WordData(
                                english=english,
                                hindi=hindi,
                                phonetic=item.get("phonetic", f"/{english.lower()}/"),
                                category=item.get("category", "general"),
                                difficulty=item.get("difficulty", 1),
                                example_sentence=item.get("example_sentence", f"This is {english}."),
                                mnemonic=item.get("mnemonic", f"Remember {english}"),
                                image_hint=item.get("image_hint", item.get("emoji", "📝"))
                            )
                            word_list.append(word)
                
                if word_list:
                    title = "Unknown Story"
                    if isinstance(data, dict) and "title" in data:
                        title = data["title"]
                    else:
                        title = os.path.basename(file_path).replace(".json", "").title()
                    
                    stories.append({
                        "filename": file_path,
                        "title": f"{title} ({len(word_list)} words)",
                        "content": word_list
                    })
                    
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
    
    # If no stories loaded, use test data
    if not stories:
        word_list = []
        for item in test_data:
            word = WordData(
                english=item["english"],
                hindi=item["hindi"],
                phonetic=f"/{item['english'].lower()}/",
                category="general",
                difficulty=1,
                example_sentence=f"This is {item['english']}.",
                mnemonic=f"Remember {item['english']}",
                image_hint=item["emoji"]
            )
            word_list.append(word)
        
        stories.append({
            "filename": "test_data.json",
            "title": "Basic Words (10 words)",
            "content": word_list
        })
    
    return stories

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # Clear session state completely at start
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.set_page_config(page_title="Bilingual Master", layout="wide")
    
    # Initialize managers
    storage = StorageManager()
    audio_mgr = AudioManager()
    profile, saved_words = storage.load()
    
    # Simple CSS
    st.markdown("""
    <style>
        .word-card {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 20px;
            text-align: center;
            margin: 20px 0;
            border: 2px solid #4f46e5;
        }
        .english-word {
            font-size: 3rem;
            font-weight: bold;
            color: #4f46e5;
            margin-bottom: 10px;
        }
        .hindi-word {
            font-size: 2.5rem;
            color: #0ea5e9;
            margin-bottom: 5px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Load stories
    stories = load_stories_from_files()
    
    # Title
    st.title("📚 Bilingual Master")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        # Dark mode toggle
        if st.button("🌙 Toggle Dark Mode"):
            profile.dark_mode = not profile.dark_mode
            storage.save(profile, [])
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Select Story")
        
        if stories:
            story_options = [s['title'] for s in stories]
            selected_story_idx = st.selectbox("Choose a story:", range(len(stories)), 
                                            format_func=lambda i: stories[i]['title'])
            
            current_story = stories[selected_story_idx]
            current_words = current_story['content']
            
            # Show story info
            st.markdown(f"**Words:** {len(current_words)}")
            
            # Debug: Show first few words
            if st.checkbox("Show word list"):
                for i, word in enumerate(current_words[:10]):
                    st.write(f"{i+1}. {word.english} → {word.hindi}")
        else:
            st.warning("No stories found")
            current_words = []
        
        st.markdown("---")
        
        # File upload
        uploaded_file = st.file_uploader("Upload JSON story", type=["json"])
        if uploaded_file:
            try:
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"Uploaded {uploaded_file.name}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    # Main content - Always show tabs even if no stories
    tab1, tab2, tab3 = st.tabs(["📖 Learn", "🎴 Review", "🧠 Quiz"])
    
    with tab1:
        if stories and current_words:
            st.markdown(f"### {current_story['title']}")
            
            # Initialize session state for this tab
            if 'learn_index' not in st.session_state:
                st.session_state.learn_index = 0
                st.session_state.show_meaning = False
            
            idx = st.session_state.learn_index
            if idx >= len(current_words):
                idx = 0
                st.session_state.learn_index = 0
            
            word = current_words[idx]
            
            # Navigation
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("⬅️ Previous", disabled=idx==0):
                    st.session_state.learn_index -= 1
                    st.session_state.show_meaning = False
                    st.rerun()
            with col3:
                if st.button("Next ➡️", disabled=idx==len(current_words)-1):
                    st.session_state.learn_index += 1
                    st.session_state.show_meaning = False
                    st.rerun()
            with col2:
                st.progress((idx + 1) / len(current_words))
                st.caption(f"Word {idx + 1} of {len(current_words)}")
            
            # Word display
            st.markdown(f"""
            <div class="word-card">
                <div style="font-size: 4rem;">{word.image_hint}</div>
                <div class="english-word">{word.english}</div>
                <div style="font-size: 1.2rem; opacity: 0.7;">{word.phonetic}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Audio
            audio_bytes = audio_mgr.get_audio_bytes(word.english, slow=True)
            if audio_bytes:
                b64_audio = base64.b64encode(audio_bytes).decode()
                audio_html = f"""
                <div style="margin: 20px 0;">
                    <audio controls style="width: 100%;">
                        <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mpeg">
                    </audio>
                </div>
                """
                st.markdown(audio_html, unsafe_allow_html=True)
            
            # Show meaning button
            if st.button("Show Meaning", type="secondary", use_container_width=True):
                st.session_state.show_meaning = True
                st.rerun()
            
            # Show meaning if revealed
            if st.session_state.get('show_meaning', False):
                st.markdown(f"""
                <div style="text-align: center; padding: 20px; background: #e1f5fe; border-radius: 10px;">
                    <div class="hindi-word">{word.hindi}</div>
                    <p style="font-style: italic; margin: 10px 0;">{word.example_sentence}</p>
                    <div style="background: white; padding: 10px; border-radius: 5px;">
                        💡 <strong>Tip:</strong> {word.mnemonic}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Sentence audio
                if word.example_sentence:
                    sent_audio = audio_mgr.get_audio_bytes(word.example_sentence)
                    if sent_audio:
                        b64_sent = base64.b64encode(sent_audio).decode()
                        sent_html = f"""
                        <div style="margin: 20px 0;">
                            <p><strong>Sentence Audio:</strong></p>
                            <audio controls style="width: 100%;">
                                <source src="data:audio/mp3;base64,{b64_sent}" type="audio/mpeg">
                            </audio>
                        </div>
                        """
                        st.markdown(sent_html, unsafe_allow_html=True)
        else:
            st.info("No words available. Upload a JSON file or the app will use test data.")
    
    with tab2:
        if stories and current_words:
            st.markdown("### Flashcards")
            
            # Filter words that need review
            review_words = [w for w in current_words if not w.last_reviewed or 
                          (datetime.now() - w.last_reviewed).days > 0]
            
            if not review_words:
                review_words = current_words[:5]
            
            if 'flashcard_index' not in st.session_state:
                st.session_state.flashcard_index = 0
                st.session_state.flashcard_show = False
            
            idx = st.session_state.flashcard_index % len(review_words)
            word = review_words[idx]
            
            # Flashcard
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"""
                <div class="word-card" style="min-height: 300px; display: flex; align-items: center; justify-content: center;">
                    <div>
                        <div class="english-word">{word.english}</div>
                        <div style="font-size: 3rem;">{word.image_hint}</div>
                        {f'<div class="hindi-word">{word.hindi}</div>' if st.session_state.flashcard_show else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if st.button("🔊 Play", use_container_width=True):
                    audio_bytes = audio_mgr.get_audio_bytes(word.english)
                    if audio_bytes:
                        b64_audio = base64.b64encode(audio_bytes).decode()
                        audio_html = f"""
                        <div style="margin: 10px 0;">
                            <audio controls style="width: 100%;">
                                <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mpeg">
                            </audio>
                        </div>
                        """
                        st.markdown(audio_html, unsafe_allow_html=True)
            
            # Controls
            if not st.session_state.flashcard_show:
                if st.button("Show Answer", type="primary", use_container_width=True):
                    st.session_state.flashcard_show = True
                    st.rerun()
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("❌ Hard", use_container_width=True):
                        word.mastery_level = max(0, word.mastery_level - 0.1)
                        word.last_reviewed = datetime.now()
                        st.session_state.flashcard_index += 1
                        st.session_state.flashcard_show = False
                        storage.save(profile, current_words)
                        st.rerun()
                with col2:
                    if st.button("🟡 Good", use_container_width=True):
                        word.mastery_level = min(1.0, word.mastery_level + 0.1)
                        word.last_reviewed = datetime.now()
                        st.session_state.flashcard_index += 1
                        st.session_state.flashcard_show = False
                        storage.save(profile, current_words)
                        st.rerun()
                with col3:
                    if st.button("✅ Easy", use_container_width=True):
                        word.mastery_level = min(1.0, word.mastery_level + 0.2)
                        word.last_reviewed = datetime.now()
                        st.session_state.flashcard_index += 1
                        st.session_state.flashcard_show = False
                        storage.save(profile, current_words)
                        st.rerun()
        else:
            st.info("No words available for flashcards.")
    
    with tab3:
        if stories and len(current_words) >= 4:
            st.markdown("### Quiz")
            
            if 'quiz_index' not in st.session_state:
                st.session_state.quiz_index = 0
                st.session_state.quiz_score = 0
                st.session_state.quiz_questions = random.sample(current_words, min(10, len(current_words)))
            
            if st.session_state.quiz_index >= len(st.session_state.quiz_questions):
                st.success(f"Quiz complete! Score: {st.session_state.quiz_score}/{len(st.session_state.quiz_questions)}")
                if st.button("Start New Quiz"):
                    st.session_state.quiz_index = 0
                    st.session_state.quiz_score = 0
                    st.session_state.quiz_questions = random.sample(current_words, min(10, len(current_words)))
                    st.rerun()
            else:
                word = st.session_state.quiz_questions[st.session_state.quiz_index]
                
                st.markdown(f"#### Question {st.session_state.quiz_index + 1}")
                st.markdown(f"<h2 style='text-align: center;'>{word.english}</h2>", unsafe_allow_html=True)
                
                # Audio
                if st.button("🔊 Play Word"):
                    audio_bytes = audio_mgr.get_audio_bytes(word.english)
                    if audio_bytes:
                        b64_audio = base64.b64encode(audio_bytes).decode()
                        audio_html = f"""
                        <div style="margin: 10px 0;">
                            <audio controls style="width: 100%;">
                                <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mpeg">
                            </audio>
                        </div>
                        """
                        st.markdown(audio_html, unsafe_allow_html=True)
                
                # Options
                options = [word.hindi]
                other_words = [w for w in current_words if w != word]
                options.extend(random.sample([w.hindi for w in other_words], 3))
                random.shuffle(options)
                
                selected = st.radio("Select the correct meaning:", options, key=f"quiz_{st.session_state.quiz_index}")
                
                if st.button("Submit Answer"):
                    if selected == word.hindi:
                        st.session_state.quiz_score += 1
                        st.success("Correct! ✅")
                    else:
                        st.error(f"Wrong! The correct answer is: {word.hindi}")
                    
                    time.sleep(1)
                    st.session_state.quiz_index += 1
                    st.rerun()
        else:
            st.info("Need at least 4 words for a quiz.")

if __name__ == "__main__":
    main()

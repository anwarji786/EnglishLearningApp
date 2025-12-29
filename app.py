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
# STORY LOADER
# ============================================================================

def load_stories_from_files():
    """Load stories from JSON files or use test data."""
    stories = []
    
    # Test data - will be used if no JSON files
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
    
    # Try to load actual JSON files
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
                elif isinstance(data, dict) and "data" in data:
                    items = data["data"]
                else:
                    items = []
                
                for item in items:
                    if isinstance(item, dict):
                        # Get English word
                        english = ""
                        for key in ["english", "English", "word", "Word", "text", "en"]:
                            if key in item and item[key]:
                                english = str(item[key]).strip()
                                break
                        
                        if english:
                            # Get Hindi
                            hindi = ""
                            for key in ["hindi", "Hindi", "translation", "meaning", "hi"]:
                                if key in item and item[key]:
                                    hindi = str(item[key]).strip()
                                    break
                            
                            if not hindi:
                                hindi = f"Translation for {english}"
                            
                            # Create word
                            word = WordData(
                                english=english,
                                hindi=hindi,
                                phonetic=item.get("phonetic", item.get("pronunciation", f"/{english.lower()}/")),
                                category=item.get("category", "general"),
                                difficulty=item.get("difficulty", 1),
                                example_sentence=item.get("example_sentence", item.get("example", f"This is {english}.")),
                                mnemonic=item.get("mnemonic", item.get("tip", f"Remember {english}")),
                                image_hint=item.get("image_hint", item.get("emoji", item.get("icon", "📝")))
                            )
                            word_list.append(word)
                
                if word_list:
                    title = "Unknown Story"
                    if isinstance(data, dict):
                        title = data.get("title", data.get("name", os.path.basename(file_path).replace(".json", "").title()))
                    else:
                        title = os.path.basename(file_path).replace(".json", "").replace("_", " ").title()
                    
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
    st.set_page_config(page_title="Bilingual Master", layout="wide")
    
    # Initialize managers
    storage = StorageManager()
    audio_mgr = AudioManager()
    profile, saved_words = storage.load()
    
    # Clear problematic session state on first run
    if 'app_initialized' not in st.session_state:
        st.session_state.app_initialized = True
        # Clear only specific problematic keys
        keys_to_clear = ['learn_index', 'show_meaning', 'flashcard_index', 
                        'flashcard_show', 'quiz_index', 'quiz_score', 'quiz_questions']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
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
        .stButton > button {
            width: 100%;
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
                                            format_func=lambda i: stories[i]['title'],
                                            key="story_selector")
            
            current_story = stories[selected_story_idx]
            current_words = current_story['content']
            
            # Show story info
            st.markdown(f"**Words:** {len(current_words)}")
            
            # Debug button to reset session
            if st.button("🔄 Reset Session State", key="reset_session"):
                keys_to_reset = ['learn_index', 'show_meaning', 'flashcard_index', 
                               'flashcard_show', 'quiz_index', 'quiz_score', 'quiz_questions']
                for key in keys_to_reset:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
                
        else:
            st.warning("No stories found")
            current_words = []
        
        st.markdown("---")
        
        # File upload
        uploaded_file = st.file_uploader("Upload JSON story", type=["json"], key="file_uploader")
        if uploaded_file:
            try:
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"Uploaded {uploaded_file.name}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["📖 Learn", "🎴 Review", "🧠 Quiz"])
    
    # TAB 1: LEARN
    with tab1:
        if stories and current_words:
            st.markdown(f"### {current_story['title'].split('(')[0].strip()}")
            
            # Initialize session state for learning
            if 'learn_index' not in st.session_state:
                st.session_state.learn_index = 0
            if 'show_meaning' not in st.session_state:
                st.session_state.show_meaning = False
            
            idx = st.session_state.learn_index
            if idx >= len(current_words):
                st.session_state.learn_index = 0
                idx = 0
            
            word = current_words[idx]
            
            # Navigation buttons - FIXED
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                prev_button = st.button("⬅️ Previous", 
                                      disabled=(idx == 0),
                                      key=f"prev_{idx}",
                                      use_container_width=True)
                if prev_button:
                    st.session_state.learn_index -= 1
                    st.session_state.show_meaning = False
                    st.rerun()
            
            with col3:
                next_button = st.button("Next ➡️", 
                                      disabled=(idx == len(current_words)-1),
                                      key=f"next_{idx}",
                                      use_container_width=True)
                if next_button:
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
            
            # Audio player
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
            
            # Show meaning button - FIXED
            show_meaning_col1, show_meaning_col2 = st.columns([3, 1])
            with show_meaning_col1:
                reveal_button = st.button("Show Meaning", 
                                        type="secondary", 
                                        key=f"reveal_{idx}",
                                        use_container_width=True)
                if reveal_button:
                    st.session_state.show_meaning = not st.session_state.show_meaning
                    st.rerun()
            
            # Show meaning if revealed
            if st.session_state.show_meaning:
                st.markdown(f"""
                <div style="text-align: center; padding: 20px; background: #e1f5fe; border-radius: 10px; margin-top: 20px;">
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
    
    # TAB 2: REVIEW (Flashcards)
    with tab2:
        if stories and current_words:
            st.markdown("### Flashcards")
            
            # Initialize session state for flashcards
            if 'flashcard_index' not in st.session_state:
                st.session_state.flashcard_index = 0
            if 'flashcard_show' not in st.session_state:
                st.session_state.flashcard_show = False
            
            # Get words for review
            review_words = current_words[:10]  # Just use first 10 words for simplicity
            
            if review_words:
                idx = st.session_state.flashcard_index % len(review_words)
                word = review_words[idx]
                
                # Flashcard display
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
                    play_button = st.button("🔊 Play", 
                                          key=f"fc_play_{idx}",
                                          use_container_width=True)
                    if play_button:
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
                
                # Flashcard controls
                if not st.session_state.flashcard_show:
                    show_answer_button = st.button("Show Answer", 
                                                 type="primary", 
                                                 key=f"fc_show_{idx}",
                                                 use_container_width=True)
                    if show_answer_button:
                        st.session_state.flashcard_show = True
                        st.rerun()
                else:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        hard_button = st.button("❌ Hard", 
                                              key=f"fc_hard_{idx}",
                                              use_container_width=True)
                        if hard_button:
                            word.mastery_level = max(0, word.mastery_level - 0.1)
                            word.last_reviewed = datetime.now()
                            st.session_state.flashcard_index += 1
                            st.session_state.flashcard_show = False
                            storage.save(profile, current_words)
                            st.rerun()
                    
                    with col2:
                        good_button = st.button("🟡 Good", 
                                              key=f"fc_good_{idx}",
                                              use_container_width=True)
                        if good_button:
                            word.mastery_level = min(1.0, word.mastery_level + 0.1)
                            word.last_reviewed = datetime.now()
                            st.session_state.flashcard_index += 1
                            st.session_state.flashcard_show = False
                            storage.save(profile, current_words)
                            st.rerun()
                    
                    with col3:
                        easy_button = st.button("✅ Easy", 
                                              key=f"fc_easy_{idx}",
                                              use_container_width=True)
                        if easy_button:
                            word.mastery_level = min(1.0, word.mastery_level + 0.2)
                            word.last_reviewed = datetime.now()
                            st.session_state.flashcard_index += 1
                            st.session_state.flashcard_show = False
                            storage.save(profile, current_words)
                            st.rerun()
            else:
                st.info("No words available for flashcards.")
        else:
            st.info("No words available for flashcards.")
    
    # TAB 3: QUIZ
    with tab3:
        if stories and len(current_words) >= 4:
            st.markdown("### Quiz")
            
            # Initialize session state for quiz
            if 'quiz_index' not in st.session_state:
                st.session_state.quiz_index = 0
                st.session_state.quiz_score = 0
                st.session_state.quiz_questions = random.sample(current_words, min(10, len(current_words)))
            
            # Check if quiz is complete
            if st.session_state.quiz_index >= len(st.session_state.quiz_questions):
                st.success(f"🎉 Quiz complete! Score: {st.session_state.quiz_score}/{len(st.session_state.quiz_questions)}")
                new_quiz_button = st.button("Start New Quiz", key="new_quiz")
                if new_quiz_button:
                    st.session_state.quiz_index = 0
                    st.session_state.quiz_score = 0
                    st.session_state.quiz_questions = random.sample(current_words, min(10, len(current_words)))
                    st.rerun()
            else:
                word = st.session_state.quiz_questions[st.session_state.quiz_index]
                
                st.markdown(f"#### Question {st.session_state.quiz_index + 1}")
                st.markdown(f"<h2 style='text-align: center;'>{word.english}</h2>", unsafe_allow_html=True)
                
                # Audio button
                play_button = st.button("🔊 Play Word", key=f"quiz_play_{st.session_state.quiz_index}")
                if play_button:
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
                
                # Quiz options
                options = [word.hindi]
                other_words = [w for w in current_words if w != word]
                options.extend(random.sample([w.hindi for w in other_words], 3))
                random.shuffle(options)
                
                selected = st.radio("Select the correct meaning:", 
                                   options, 
                                   key=f"quiz_option_{st.session_state.quiz_index}")
                
                submit_button = st.button("Submit Answer", 
                                        type="primary", 
                                        key=f"quiz_submit_{st.session_state.quiz_index}")
                if submit_button:
                    if selected == word.hindi:
                        st.session_state.quiz_score += 1
                        st.success("Correct! ✅")
                    else:
                        st.error(f"Wrong! The correct answer is: {word.hindi}")
                    
                    time.sleep(1)
                    st.session_state.quiz_index += 1
                    st.rerun()
        else:
            st.info(f"Need at least 4 words for a quiz. You have {len(current_words) if current_words else 0} words.")

if __name__ == "__main__":
    main()

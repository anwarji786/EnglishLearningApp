import streamlit as st
import json
import time
import random
from pathlib import Path
from gtts import gTTS
import io
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any, Tuple
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

    @property
    def needs_review(self) -> bool:
        if not self.last_reviewed:
            return True
        days_since = (datetime.now() - self.last_reviewed).days
        interval = max(1, int(self.review_count ** 1.5))
        return days_since >= interval

    def update_mastery(self, correct: bool):
        self.review_count += 1
        self.last_reviewed = datetime.now()
        if correct:
            self.mastery_level = min(1.0, self.mastery_level + 0.15)
        else:
            self.mastery_level = max(0.0, self.mastery_level - 0.1)

@dataclass
class UserProfile:
    name: str = "Learner"
    dark_mode: bool = False
    auto_play_story: bool = False
    daily_goal: int = 10

# ============================================================================
# STORAGE & ENGINE
# ============================================================================

class StorageManager:
    def __init__(self):
        self.data_dir = Path("learning_data")
        self.data_dir.mkdir(exist_ok=True)
    
    def save(self, profile: UserProfile, all_words: List[WordData]):
        data = {
            "profile": asdict(profile),
            "words": [asdict(w) for w in all_words],
            "timestamp": datetime.now().isoformat()
        }
        with open(self.data_dir / "user_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def load(self) -> Tuple[UserProfile, List[WordData]]:
        try:
            with open(self.data_dir / "user_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = UserProfile(**data["profile"])
            words = []
            for w in data["words"]:
                if w.get('last_reviewed'): w['last_reviewed'] = datetime.fromisoformat(w['last_reviewed'])
                words.append(WordData(**w))
            return profile, words
        except FileNotFoundError:
            return UserProfile(), []

# ============================================================================
# AUDIO MANAGER (Fixed with st.empty)
# ============================================================================

class AudioManager:
    def __init__(self):
        self.cache_dir = Path("audio_cache")
        self.cache_dir.mkdir(exist_ok=True)

    def get_audio_bytes(self, text: str, slow: bool = False) -> Optional[bytes]:
        """Generate or retrieve audio from cache."""
        if not text: return None
        
        clean_text = text.strip()
        if not clean_text: return None

        # Create unique hash based on content AND speed setting
        hash_key = hashlib.md5(f"{clean_text}_{slow}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{hash_key}.mp3"

        # Return from cache if exists
        if cache_file.exists():
            return cache_file.read_bytes()

        # Generate new audio
        try:
            tts = gTTS(text=clean_text, lang="en", slow=slow)
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            audio_data = mp3_fp.read()
            
            # Save to cache
            cache_file.write_bytes(audio_data)
            return audio_data
        except Exception as e:
            st.error(f"Audio Error for '{text}': {e}")
            return None

    def render_player(self, placeholder, audio_bytes: bytes, label: str, unique_id: str, word_text: str):
        """
        Renders HTML5 audio player.
        placeholder: A st.empty() object to force DOM refresh.
        """
        if not audio_bytes: return
        
        b64_audio = base64.b64encode(audio_bytes).decode()
        html = f"""
        <div style="background: #f1f3f5; padding: 10px; border-radius: 10px; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #495057; margin-bottom: 5px;">🔊 {label} ({word_text})</div>
            <audio id="audio_{unique_id}" controls style="width: 100%; height: 35px;">
                <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mpeg">
            </audio>
            <div style="display: flex; gap: 5px; margin-top: 8px;">
                <button onclick="document.getElementById('audio_{unique_id}').play()" style="flex:1; background:#4CAF50; color:white; border:none; padding:8px; border-radius:5px;">▶ Play</button>
                <button onclick="document.getElementById('audio_{unique_id}').pause()" style="flex:1; background:#FF9800; color:white; border:none; padding:8px; border-radius:5px;">⏸ Pause</button>
                <button onclick="
                    var aud = document.getElementById('audio_{unique_id}');
                    aud.currentTime = 0; 
                    aud.play(); 
                    aud.onended = function() {{ aud.currentTime = 0; aud.play(); }}; 
                    " style="flex:1; background:#2196F3; color:white; border:none; padding:8px; border-radius:5px;">🔁 Loop</button>
            </div>
        </div>
        """
        # FIXED: Use placeholder to force DOM refresh. Removed 'key' from markdown.
        placeholder.empty()
        placeholder.markdown(html, unsafe_allow_html=True)

# ============================================================================
# STORY & DATA LOADER
# ============================================================================

def load_stories_from_files():
    stories = []
    files = glob.glob("*.json")
    # Filter out system files
    files = [f for f in files if os.path.basename(f) not in ["user_data.json", "requirements.txt"]]
    
    emoji_map = {
        "pronoun": "👤", "verb": "🏃", "noun": "📦", "adjective": "🎨", "article": "🔤"
    }
    default_emojis = {
        "cat": "🐱", "dog": "🐶", "house": "🏠", "eat": "🍎", "happy": "😊", "run": "🏃‍♂️"
    }

    for filepath in sorted(files):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            word_list = []
            for item in data.get("content", []):
                eng = item.get("english", "")
                if not eng: continue
                
                cat = item.get("category", "general").lower()
                if "pronoun" in eng.lower() or eng in ["I", "you", "he"]: cat = "pronoun"
                elif eng in default_emojis: pass
                else: cat = "noun"

                emoji = item.get("image_hint", emoji_map.get(cat, "📝"))
                if eng.lower() in default_emojis: emoji = default_emojis[eng.lower()]

                w = WordData(
                    english=eng,
                    hindi=item.get("hindi", ""),
                    phonetic=item.get("phonetic", "/?/"),
                    category=cat,
                    difficulty=item.get("difficulty", 1),
                    example_sentence=item.get("example_sentence", f"This is {eng}."),
                    mnemonic=item.get("mnemonic", f"Think of {eng}"),
                    image_hint=emoji
                )
                word_list.append(w)
            
            stories.append({
                "filename": filepath,
                "title": data.get("title", os.path.basename(filepath)),
                "level": data.get("level", "Beginner"),
                "content": word_list
            })
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    
    return stories

# ============================================================================
# UI COMPONENTS
# ============================================================================

def load_custom_css(dark_mode: bool):
    bg = "#121212" if dark_mode else "#ffffff"
    text = "#e0e0e0" if dark_mode else "#333333"
    card_bg = "#1e1e1e" if dark_mode else "#f8f9fa"
    primary = "#6200ea" if dark_mode else "#4f46e5"
    accent = "#03dac6" if dark_mode else "#0ea5e9"
    
    st.markdown(f"""
    <style>
        .stApp {{ background-color: {bg}; color: {text}; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
        .stTabs [data-baseweb="tab"] {{ background-color: {card_bg}; border-radius: 10px 10px 0 0; padding: 15px; font-weight: bold; }}
        
        @media (max-width: 768px) {{
            .stApp {{ padding-top: 0; }}
            .block-container {{ padding: 1rem !important; }}
            .stMarkdown {{ font-size: 110%; }}
            h1 {{ font-size: 1.8rem !important; }}
            h2 {{ font-size: 1.5rem !important; }}
            button {{ width: 100%; margin-bottom: 5px; }}
        }}

        .word-card {{
            background: {card_bg};
            padding: 25px;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            border: 2px solid {primary};
        }}
        .english-word {{ font-size: 3rem; font-weight: bold; color: {primary}; margin-bottom: 10px; }}
        .hindi-word {{ font-size: 2.5rem; color: {accent}; margin-bottom: 5px; }}
        .phonetic {{ font-size: 1.2rem; opacity: 0.7; }}
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# APP LOGIC MODES
# ============================================================================

def mode_story_reader(story_data: List[WordData], story_filename: str, audio_mgr: AudioManager, storage: StorageManager, profile: UserProfile):
    
    # Init State
    if 'reader_filename' not in st.session_state or st.session_state['reader_filename'] != story_filename:
        st.session_state.reader_filename = story_filename
        st.session_state.reader_idx = 0
        st.session_state.show_hindi = False

    if 'reader_idx' not in st.session_state:
        st.session_state.reader_idx = 0
        
    idx = st.session_state.reader_idx
    
    # Boundary check
    if idx >= len(story_data):
        idx = len(story_data) - 1
        st.session_state.reader_idx = idx
    
    # Navigation
    col_prev, col_center, col_next = st.columns([1, 3, 1])
    
    with col_prev:
        if st.button("⬅️ Prev", disabled=(idx == 0), use_container_width=True, key="btn_prev"):
            st.session_state.reader_idx -= 1
            st.session_state.show_hindi = False
            st.rerun()
            
    with col_next:
        if st.button("Next ➡️", disabled=(idx == len(story_data)-1), use_container_width=True, key="btn_next"):
            st.session_state.reader_idx += 1
            st.session_state.show_hindi = False
            st.rerun()

    with col_center:
        st.progress((idx + 1) / len(story_data))
        st.caption(f"Word {idx+1} of {len(story_data)}")

    word = story_data[idx]
    
    # FIXED: Create placeholder for audio to force refresh
    audio_placeholder = st.empty()

    # Audio Logic
    audio_bytes = audio_mgr.get_audio_bytes(word.english, slow=True)
    
    # Display Card
    st.markdown(f"""
    <div class="word-card">
        <div style="font-size: 4rem;">{word.image_hint}</div>
        <div class="english-word">{word.english}</div>
        <div class="phonetic">{word.phonetic}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Render Player
    if audio_bytes:
        audio_mgr.render_player(audio_placeholder, audio_bytes, "Listen", f"reader_audio_{idx}", word.english)
    
    if st.button("👁️ Show Meaning & Context", use_container_width=True, type="secondary", key="btn_reveal"):
        st.session_state.show_hindi = not st.session_state.show_hindi
        st.rerun()
        
    if st.session_state.show_hindi:
        st.markdown(f"""
        <div style="text-align: center; background: rgba(0,0,0,0.05); padding: 15px; border-radius: 10px;">
            <div class="hindi-word">{word.hindi}</div>
            <p style="font-style: italic; margin-top: 10px;">{word.example_sentence}</p>
            <div style="background: #e1f5fe; color: #0277bd; padding: 10px; border-radius: 5px; margin-top:10px;">
                💡 <strong>Tip:</strong> {word.mnemonic}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if word.example_sentence:
            sent_audio = audio_mgr.get_audio_bytes(word.example_sentence, slow=False)
            if sent_audio:
                st.markdown("**🗣️ Sentence Audio:**")
                # Another placeholder for sentence audio
                sent_placeholder = st.empty()
                audio_mgr.render_player(sent_placeholder, sent_audio, "Listen to Sentence", f"reader_sent_{idx}", "sentence")

def mode_flashcards(words: List[WordData], audio_mgr: AudioManager, engine: StorageManager):
    due_words = sorted([w for w in words if w.needs_review], key=lambda x: x.mastery_level)[:10]
    
    if not due_words:
        st.success("🎉 No words due for review!")
        return

    st.subheader(f"📝 Review Session: {len(due_words)} Cards")
    
    if 'fc_idx' not in st.session_state or st.session_state.get('fc_dirty', False):
        st.session_state.fc_idx = 0
        st.session_state.fc_dirty = False
        st.session_state.fc_reveal = False

    if st.session_state.fc_idx >= len(due_words):
        st.balloons()
        st.success("Session Complete!")
        if st.button("Start New Session"):
            st.session_state.fc_idx = 0
            st.session_state.fc_dirty = True
            st.rerun()
        return

    word = due_words[st.session_state.fc_idx]
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"""
        <div class="word-card" style="min-height: 200px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
            <div class="english-word">{word.english}</div>
            <div style="font-size: 2rem;">{word.image_hint}</div>
            {f'<div class="hindi-word">{word.hindi}</div>' if st.session_state.fc_reveal else ''}
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Flashcard audio placeholder
        fc_audio_placeholder = st.empty()
        if st.button("🔊 Play", key="fc_play", use_container_width=True):
            audio = audio_mgr.get_audio_bytes(word.english)
            if audio: audio_mgr.render_player(fc_audio_placeholder, audio, "Word", f"fc_aud_{st.session_state.fc_idx}", word.english)

    if not st.session_state.fc_reveal:
        if st.button("Show Answer", use_container_width=True, type="primary"):
            st.session_state.fc_reveal = True
            st.rerun()
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("❌ Hard", use_container_width=True):
                word.update_mastery(False)
                st.session_state.fc_idx += 1
                st.session_state.fc_reveal = False
                st.rerun()
        with c2:
            if st.button("🟡 Good", use_container_width=True):
                word.update_mastery(True)
                st.session_state.fc_idx += 1
                st.session_state.fc_reveal = False
                st.rerun()
        with c3:
            if st.button("✅ Easy", use_container_width=True):
                word.update_mastery(True)
                st.session_state.fc_idx += 1
                st.session_state.fc_reveal = False
                st.rerun()

def mode_quiz(words: List[WordData], audio_mgr: AudioManager):
    if len(words) < 4: return st.info("Need at least 4 words.")
    
    if 'quiz_q_idx' not in st.session_state:
        st.session_state.quiz_questions = random.sample(words, min(10, len(words)))
        st.session_state.quiz_q_idx = 0
        st.session_state.quiz_score = 0

    if st.session_state.quiz_q_idx >= len(st.session_state.quiz_questions):
        st.success(f"Quiz Finished! Score: {st.session_state.quiz_score}/{len(st.session_state.quiz_questions)}")
        if st.button("New Quiz"):
            del st.session_state.quiz_q_idx
            st.rerun()
        return

    current_q = st.session_state.quiz_questions[st.session_state.quiz_q_idx]
    
    st.markdown(f"### Question {st.session_state.quiz_q_idx + 1}")
    st.markdown(f"<h2 style='text-align: center;'>{current_q.english}</h2>", unsafe_allow_html=True)
    
    # Quiz audio placeholder
    quiz_audio_placeholder = st.empty()
    audio = audio_mgr.get_audio_bytes(current_q.english)
    if audio: audio_mgr.render_player(quiz_audio_placeholder, audio, "Listen", f"quiz_{st.session_state.quiz_q_idx}", current_q.english)

    correct = current_q.hindi
    options = [correct] + random.sample([w.hindi for w in words if w.hindi != correct], 3)
    random.shuffle(options)

    choice = st.radio("Select Meaning:", options)
    if st.button("Submit", use_container_width=True, type="primary"):
        if choice == correct:
            st.session_state.quiz_score += 1
            st.toast("Correct!", icon="✅")
        else:
            st.toast(f"Wrong! It was {correct}", icon="❌")
        time.sleep(0.5)
        st.session_state.quiz_q_idx += 1
        st.rerun()

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(page_title="Bilingual Master", layout="wide")
    storage = StorageManager()
    audio_mgr = AudioManager()
    profile, saved_words = storage.load()
    
    load_custom_css(profile.dark_mode)
    
    stories = load_stories_from_files()
    
    with st.container():
        col_title, col_theme = st.columns([4, 1])
        with col_title:
            st.title("📚 Bilingual Master")
        with col_theme:
            if st.button("🌙/☀️", help="Toggle Dark Mode"):
                profile.dark_mode = not profile.dark_mode
                storage.save(profile, [])
                st.rerun()

    if not stories:
        st.error("No JSON story files found. Please upload one.")
        return

    with st.sidebar:
        st.header("Settings")
        st.write(f"Hello, **{profile.name}**!")
        
        st.markdown("### Current Story")
        sel_idx = st.selectbox("Choose Story:", range(len(stories)), format_func=lambda x: stories[x]['title'])
        
        if st.button("🔄 Reload Files"):
            st.rerun()

        st.markdown("---")
        st.file_uploader("Upload JSON Story", type=["json"], key="uploader")

    current_story_words = stories[sel_idx]['content']
    current_story_filename = stories[sel_idx]['filename']
    
    saved_map = {w.english: w for w in saved_words}
    for w in current_story_words:
        if w.english in saved_map:
            w.mastery_level = saved_map[w.english].mastery_level
            w.review_count = saved_map[w.english].review_count
            w.last_reviewed = saved_map[w.english].last_reviewed

    def save_current():
        storage.save(profile, current_story_words)

    tab1, tab2, tab3, tab4 = st.tabs(["📖 Story Reader", "🎴 Flashcards", "🧠 Quiz", "📊 Stats"])
    
    with tab1:
        st.markdown(f"### Reading: {stories[sel_idx]['title']}")
        mode_story_reader(current_story_words, current_story_filename, audio_mgr, storage, profile)
        save_current()

    with tab2:
        mode_flashcards(current_story_words, audio_mgr, storage)
        save_current()

    with tab3:
        mode_quiz(current_story_words, audio_mgr)

    with tab4:
        st.header("📊 Learning Progress")
        learned = sum(1 for w in current_story_words if w.mastery_level >= 0.8)
        due = sum(1 for w in current_story_words if w.needs_review)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Words", len(current_story_words))
        c2.metric("Mastered (80%+)", learned)
        c3.metric("Due for Review", due)
        
        import pandas as pd
        df = pd.DataFrame([{"Word": w.english, "Mastery": w.mastery_level} for w in current_story_words])
        st.bar_chart(df.set_index("Word"))

if __name__ == "__main__":
    main()

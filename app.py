import streamlit as st
import json
import time
import random
import uuid
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
# AUDIO MANAGER
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
            st.error(f"Audio Error for '{text}': {e}")
            return None

    def render_player(self, audio_bytes: bytes, word_text: str) -> str:
        """Returns HTML for audio player."""
        if not audio_bytes: return ""
        
        unique_id = f"audio_{uuid.uuid4().hex[:8]}"
        b64_audio = base64.b64encode(audio_bytes).decode()
        
        html = f"""
        <div style="background: #f1f3f5; padding: 15px; border-radius: 10px; margin: 15px 0; border: 1px solid #dee2e6;">
            <div style="font-size: 1.1rem; color: #333; margin-bottom: 10px; font-weight: bold;">
                🔊 Listen to: <span style="color:#666; font-weight:normal;">"{word_text}"</span>
            </div>
            <audio id="{unique_id}" controls style="width: 100%; height: 40px; margin-bottom: 10px;">
                <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </div>
        """
        return html

# ============================================================================
# SIMPLE STORY LOADER - FIXED VERSION
# ============================================================================

def load_stories_from_files():
    """Load all JSON story files."""
    stories = []
    
    # Look for JSON files
    json_files = glob.glob("*.json")
    
    # Filter out system files
    json_files = [f for f in json_files 
                  if os.path.basename(f) not in ["user_data.json", "requirements.txt"]]
    
    print(f"Found JSON files: {json_files}")
    
    for file_path in sorted(json_files):
        try:
            print(f"\n=== Loading {file_path} ===")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            word_list = []
            
            # Print raw data structure for debugging
            print(f"Raw data type: {type(data)}")
            print(f"Raw data keys (if dict): {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Get the content array
            content = None
            if isinstance(data, dict):
                # Try to find the content array
                for key in ["content", "words", "vocabulary", "items", "data"]:
                    if key in data:
                        content = data[key]
                        print(f"Found content in key: {key}")
                        break
                
                # If still no content, maybe the dict itself is the only item
                if content is None:
                    # Check if this dict looks like a word item
                    if "english" in data or "English" in data or "word" in data:
                        content = [data]  # Wrap it in a list
                        print("Treating entire file as a single word item")
            elif isinstance(data, list):
                content = data
                print("File is a list of items")
            
            if content is None:
                print(f"WARNING: No content found in {file_path}")
                continue
            
            print(f"Content type: {type(content)}, length: {len(content) if hasattr(content, '__len__') else 'N/A'}")
            
            # Process each item
            for i, item in enumerate(content):
                try:
                    if not isinstance(item, dict):
                        print(f"  Item {i} is not a dict: {type(item)}")
                        continue
                    
                    # Get English word
                    english = ""
                    if "english" in item:
                        english = str(item["english"]).strip()
                    elif "English" in item:
                        english = str(item["English"]).strip()
                    elif "word" in item:
                        english = str(item["word"]).strip()
                    elif "text" in item:
                        english = str(item["text"]).strip()
                    elif "en" in item:
                        english = str(item["en"]).strip()
                    
                    if not english:
                        print(f"  Item {i}: No English word found, skipping")
                        continue
                    
                    print(f"  Processing word {i}: '{english}'")
                    
                    # Get Hindi translation
                    hindi = ""
                    for key in ["hindi", "Hindi", "translation", "meaning", "hi"]:
                        if key in item:
                            hindi = str(item[key]).strip()
                            break
                    
                    if not hindi:
                        hindi = f"Translation for {english}"
                    
                    # Get other fields with defaults
                    phonetic = item.get("phonetic", item.get("pronunciation", f"/{english.lower()}/"))
                    category = item.get("category", item.get("type", "general")).lower()
                    difficulty = item.get("difficulty", 1)
                    example_sentence = item.get("example_sentence", item.get("example", f"This is {english}."))
                    mnemonic = item.get("mnemonic", item.get("tip", f"Remember: {english}"))
                    
                    # Get emoji
                    emoji_keys = ["image_hint", "emoji", "icon", "symbol", "image"]
                    image_hint = "📝"
                    for key in emoji_keys:
                        if key in item:
                            image_hint = item[key]
                            break
                    
                    # Create word
                    word = WordData(
                        english=english,
                        hindi=hindi,
                        phonetic=phonetic,
                        category=category,
                        difficulty=difficulty,
                        example_sentence=example_sentence,
                        mnemonic=mnemonic,
                        image_hint=image_hint
                    )
                    word_list.append(word)
                    
                except Exception as e:
                    print(f"  Error processing item {i}: {e}")
            
            if not word_list:
                print(f"WARNING: No valid words created from {file_path}")
                continue
            
            print(f"Successfully created {len(word_list)} words")
            
            # Get title
            title = ""
            if isinstance(data, dict):
                title = data.get("title", data.get("name", os.path.basename(file_path).replace(".json", "").title()))
            else:
                title = os.path.basename(file_path).replace(".json", "").replace("_", " ").title()
            
            level = "Beginner"
            if isinstance(data, dict):
                level = data.get("level", "Beginner")
            
            stories.append({
                "filename": file_path,
                "title": f"{title} ({len(word_list)} words)",
                "level": level,
                "content": word_list
            })
            
            print(f"✅ Added story: {title} with {len(word_list)} words")
            
        except Exception as e:
            print(f"❌ ERROR loading {file_path}: {e}")
            import traceback
            traceback.print_exc()
    
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

def mode_story_reader(story_data: List[WordData], story_filename: str, audio_mgr: AudioManager):
    
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
    
    if len(story_data) == 0:
        st.warning("No words found in this story.")
        return
    
    # Navigation
    col_prev, col_center, col_next = st.columns([1, 3, 1])
    
    with col_prev:
        if st.button("⬅️ Prev", disabled=(idx == 0), use_container_width=True, key=f"btn_prev_{idx}"):
            st.session_state.reader_idx -= 1
            st.session_state.show_hindi = False
            st.rerun()
            
    with col_next:
        if st.button("Next ➡️", disabled=(idx == len(story_data)-1), use_container_width=True, key=f"btn_next_{idx}"):
            st.session_state.reader_idx += 1
            st.session_state.show_hindi = False
            st.rerun()

    with col_center:
        st.progress((idx + 1) / len(story_data))
        st.caption(f"Word {idx+1} of {len(story_data)}")

    word = story_data[idx]
    
    # Display Card
    st.markdown(f"""
    <div class="word-card">
        <div style="font-size: 4rem;">{word.image_hint}</div>
        <div class="english-word">{word.english}</div>
        <div class="phonetic">{word.phonetic}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Audio
    audio_bytes = audio_mgr.get_audio_bytes(word.english, slow=True)
    if audio_bytes:
        audio_html = audio_mgr.render_player(audio_bytes, word.english)
        st.markdown(audio_html, unsafe_allow_html=True)
    
    if st.button("👁️ Show Meaning & Context", use_container_width=True, type="secondary", key=f"btn_reveal_{idx}"):
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
                sent_html = audio_mgr.render_player(sent_audio, word.example_sentence)
                st.markdown(sent_html, unsafe_allow_html=True)

def mode_flashcards(words: List[WordData], audio_mgr: AudioManager):
    if len(words) < 1:
        st.info("No words available for flashcards.")
        return
    
    due_words = sorted([w for w in words if w.needs_review], key=lambda x: x.mastery_level)[:10]
    
    if not due_words:
        st.success("🎉 No words due for review!")
        return

    st.subheader(f"📝 Review Session: {len(due_words)} Cards")
    
    if 'fc_idx' not in st.session_state:
        st.session_state.fc_idx = 0
        st.session_state.fc_reveal = False

    if st.session_state.fc_idx >= len(due_words):
        st.balloons()
        st.success("Session Complete!")
        if st.button("Start New Session"):
            st.session_state.fc_idx = 0
            st.session_state.fc_reveal = False
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
        if st.button("🔊 Play", key=f"fc_play_{st.session_state.fc_idx}", use_container_width=True):
            audio_bytes = audio_mgr.get_audio_bytes(word.english)
            if audio_bytes:
                audio_html = audio_mgr.render_player(audio_bytes, word.english)
                st.markdown(audio_html, unsafe_allow_html=True)

    if not st.session_state.fc_reveal:
        if st.button("Show Answer", use_container_width=True, type="primary", key=f"fc_reveal_{st.session_state.fc_idx}"):
            st.session_state.fc_reveal = True
            st.rerun()
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("❌ Hard", use_container_width=True, key=f"fc_hard_{st.session_state.fc_idx}"):
                word.update_mastery(False)
                st.session_state.fc_idx += 1
                st.session_state.fc_reveal = False
                st.rerun()
        with c2:
            if st.button("🟡 Good", use_container_width=True, key=f"fc_good_{st.session_state.fc_idx}"):
                word.update_mastery(True)
                st.session_state.fc_idx += 1
                st.session_state.fc_reveal = False
                st.rerun()
        with c3:
            if st.button("✅ Easy", use_container_width=True, key=f"fc_easy_{st.session_state.fc_idx}"):
                word.update_mastery(True)
                st.session_state.fc_idx += 1
                st.session_state.fc_reveal = False
                st.rerun()

def mode_quiz(words: List[WordData], audio_mgr: AudioManager):
    if len(words) < 4: 
        st.info(f"Need at least 4 words for quiz. You have {len(words)} words.")
        return
    
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
    
    if st.button("🔊 Play Audio", key=f"quiz_play_{st.session_state.quiz_q_idx}"):
        audio_bytes = audio_mgr.get_audio_bytes(current_q.english)
        if audio_bytes:
            audio_html = audio_mgr.render_player(audio_bytes, current_q.english)
            st.markdown(audio_html, unsafe_allow_html=True)

    correct = current_q.hindi
    options = [correct] + random.sample([w.hindi for w in words if w.hindi != correct], 3)
    random.shuffle(options)

    choice = st.radio("Select Meaning:", options, key=f"quiz_choice_{st.session_state.quiz_q_idx}")
    if st.button("Submit", use_container_width=True, type="primary", key=f"quiz_submit_{st.session_state.quiz_q_idx}"):
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
    
    # Debug section - show what's in the directory
    st.sidebar.markdown("### Debug Info")
    current_dir = os.listdir(".")
    st.sidebar.write(f"Files in directory ({len(current_dir)}):")
    for file in sorted(current_dir):
        st.sidebar.write(f"- {file}")
    
    # Load stories
    with st.spinner("Loading stories..."):
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
        st.error("""
        ## No stories loaded!
        
        **Possible issues:**
        1. No JSON files in the directory
        2. JSON files have wrong format
        3. JSON files are empty
        
        **Create a simple test file named `test.json` with:**
        ```json
        [
          {
            "english": "Hello",
            "hindi": "नमस्ते"
          },
          {
            "english": "Goodbye", 
            "hindi": "अलविदा"
          }
        ]
        ```
        
        **Or with a wrapper:**
        ```json
        {
          "title": "My Story",
          "content": [
            {"english": "Hello", "hindi": "नमस्ते"},
            {"english": "Goodbye", "hindi": "अलविदा"}
          ]
        }
        ```
        """)
        
        # Try to load a test file
        test_data = [
            {"english": "Hello", "hindi": "नमस्ते", "image_hint": "👋"},
            {"english": "Goodbye", "hindi": "अलविदा", "image_hint": "👋"},
            {"english": "Thank you", "hindi": "धन्यवाद", "image_hint": "🙏"},
            {"english": "Please", "hindi": "कृपया", "image_hint": "🙏"},
            {"english": "Yes", "hindi": "हाँ", "image_hint": "✅"}
        ]
        
        test_words = []
        for item in test_data:
            word = WordData(
                english=item["english"],
                hindi=item["hindi"],
                phonetic=f"/{item['english'].lower()}/",
                category="general",
                difficulty=1,
                example_sentence=f"This is {item['english']}.",
                mnemonic=f"Remember {item['english']}",
                image_hint=item["image_hint"]
            )
            test_words.append(word)
        
        stories = [{
            "filename": "test_data.json",
            "title": "Test Words (5 words)",
            "level": "Beginner",
            "content": test_words
        }]
        
        st.warning("Using test data instead. Create a JSON file to use your own words.")

    with st.sidebar:
        st.header("Settings")
        st.write(f"Hello, **{profile.name}**!")
        
        st.markdown("### Current Story")
        story_titles = [s['title'] for s in stories]
        sel_idx = st.selectbox("Choose Story:", range(len(stories)), format_func=lambda x: story_titles[x])
        
        if st.button("🔄 Reload Files"):
            st.rerun()

        st.markdown("---")
        uploaded_file = st.file_uploader("Upload JSON Story", type=["json"], key="uploader")
        if uploaded_file is not None:
            try:
                file_path = Path(uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"Uploaded {uploaded_file.name}!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    current_story_words = stories[sel_idx]['content']
    current_story_filename = stories[sel_idx]['filename']
    
    # Merge with saved progress
    saved_map = {w.english: w for w in saved_words}
    for w in current_story_words:
        if w.english in saved_map:
            saved_w = saved_map[w.english]
            w.mastery_level = saved_w.mastery_level
            w.review_count = saved_w.review_count
            w.last_reviewed = saved_w.last_reviewed

    def save_current():
        storage.save(profile, current_story_words)

    tab1, tab2, tab3, tab4 = st.tabs(["📖 Story Reader", "🎴 Flashcards", "🧠 Quiz", "📊 Stats"])
    
    with tab1:
        st.markdown(f"### 📖 Reading: {stories[sel_idx]['title'].split('(')[0].strip()}")
        mode_story_reader(current_story_words, current_story_filename, audio_mgr)
        save_current()

    with tab2:
        mode_flashcards(current_story_words, audio_mgr)
        save_current()

    with tab3:
        mode_quiz(current_story_words, audio_mgr)

    with tab4:
        st.header("📊 Learning Progress")
        if current_story_words:
            learned = sum(1 for w in current_story_words if w.mastery_level >= 0.8)
            due = sum(1 for w in current_story_words if w.needs_review)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Words", len(current_story_words))
            c2.metric("Mastered (80%+)", learned)
            c3.metric("Due for Review", due)
            
            import pandas as pd
            df = pd.DataFrame([{"Word": w.english, "Mastery": w.mastery_level} for w in current_story_words])
            st.bar_chart(df.set_index("Word"))
            
            # Show word list
            st.markdown("### Word List")
            for i, word in enumerate(current_story_words):
                st.write(f"{i+1}. **{word.english}** → {word.hindi} (Mastery: {word.mastery_level:.0%})")
        else:
            st.warning("No words to display.")

if __name__ == "__main__":
    main()

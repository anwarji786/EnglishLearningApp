import streamlit as st
import json
import time
import random
from pathlib import Path
from gtts import gTTS
import io
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Any
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import os
import glob
import uuid

# ============================================================================
# SIMPLIFIED CONFIGURATION
# ============================================================================
class AppConfig:
    def __init__(self):
        self.config = {
            "app": {"name": "Bilingual English Master", "version": "1.1.0", "debug": False},
            "learning": {
                "daily_word_limit": 20,
                "review_limit": 10,
                "mastery_threshold": 0.8,
                "streak_reset_days": 2,
                "initial_difficulty": 1,
                "max_difficulty": 5
            },
            "audio": {
                "cache_ttl_days": 7,
                "slow_speed": True,
                "default_language": "en"
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

config = AppConfig()

# ============================================================================
# DATA MODELS
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
        if self.review_count == 0:
            interval = 1
        elif self.review_count == 1:
            interval = 2
        else:
            interval = min(int(self.review_count ** 1.3), 365)
        return days_since >= interval

    def get_mastery_badge(self) -> str:
        if self.mastery_level >= 0.9:
            return "💎"
        elif self.mastery_level >= 0.7:
            return "🟢"
        elif self.mastery_level >= 0.5:
            return "🟡"
        elif self.mastery_level >= 0.3:
            return "🟠"
        else:
            return "🔴"

@dataclass
class UserProfile:
    name: str
    total_words_learned: int = 0
    streak_days: int = 0
    last_session: Optional[datetime] = None
    preferred_difficulty: int = 1
    auto_play_audio: bool = False
    dark_mode: bool = False
    learning_pace: str = "normal"
    daily_goal: int = 10

    def to_dict(self) -> Dict:
        data = asdict(self)
        if data['last_session']:
            data['last_session'] = data['last_session'].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict):
        if data.get('last_session'):
            data['last_session'] = datetime.fromisoformat(data['last_session'])
        return cls(**data)

# ============================================================================
# STORAGE MANAGER
# ============================================================================
class LearningStorage:
    def __init__(self):
        self.data_dir = Path("learning_data")
        self.data_dir.mkdir(exist_ok=True)

    def save_progress(self, profile: UserProfile, words: List[WordData]):
        progress = {
            "profile": profile.to_dict(),
            "words": [asdict(word) for word in words],
            "timestamp": datetime.now().isoformat()
        }
        with open(self.data_dir / "progress.json", "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, default=str)

    def load_progress(self) -> Tuple[Optional[UserProfile], List[WordData]]:
        try:
            with open(self.data_dir / "progress.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = UserProfile.from_dict(data["profile"])
            words = []
            for word_dict in data["words"]:
                if word_dict.get('last_reviewed'):
                    word_dict['last_reviewed'] = datetime.fromisoformat(word_dict['last_reviewed'])
                words.append(WordData(**word_dict))
            return profile, words
        except FileNotFoundError:
            return None, []

# ============================================================================
# FIXED AUDIO MANAGER (NO LOOP, SINGLE-AUDIO ENFORCEMENT)
# ============================================================================
class AudioManager:
    def __init__(self):
        self.cache_dir = Path("audio_cache")
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_key(self, text: str, slow: bool) -> str:
        if not text:
            return ""
        key_string = f"{text}_{slow}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def generate_audio(self, text: str, slow: bool = True) -> Optional[bytes]:
        if not text or text.strip() in (".", "", None):
            return None
        cache_key = self._get_cache_key(text, slow)
        cache_file = self.cache_dir / f"{cache_key}.mp3"
        if cache_file.exists():
            return cache_file.read_bytes()
        try:
            tts = gTTS(text=text, lang='en', slow=slow)
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            audio_data = audio_bytes.read()
            cache_file.write_bytes(audio_data)
            return audio_data
        except Exception as e:
            st.error(f"Audio generation failed: {str(e)}")
            return None

    def create_audio_player(self, audio_bytes: bytes, text: str = "", context: str = "") -> None:
        if not audio_bytes:
            return

        unique_id = str(uuid.uuid4()).replace("-", "")[:12]
        active_key = f"active_audio_id_{context}" if context else "active_audio_id"
        st.session_state[active_key] = unique_id

        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode()

        js_code = f"""
        <script>
        (function() {{
            const playerId = 'audio_{unique_id}';
            const newAudio = document.getElementById(playerId);
            if (!newAudio) return;
            const allAudios = document.querySelectorAll('audio');
            allAudios.forEach(audio => {{
                if (audio.id !== playerId) {{
                    audio.pause();
                    audio.currentTime = 0;
                }}
            }});
            newAudio.currentTime = 0;
            newAudio.load();
            newAudio.onended = null;
        }})();
        </script>
        """

        html_code = f"""
        <div style="margin: 10px 0;">
            <audio id="audio_{unique_id}" src="data:audio/mp3;base64,{audio_b64}" preload="auto" controls></audio>
        </div>
        """

        st.markdown(html_code + js_code, unsafe_allow_html=True)

    def clear_cache(self):
        for file in self.cache_dir.glob("*.mp3"):
            try:
                file.unlink()
            except Exception:
                pass
        st.success("Audio cache cleared!")

# ============================================================================
# LEARNING ENGINE
# ============================================================================
class LearningEngine:
    def __init__(self):
        self.storage = LearningStorage()
        self.audio_manager = AudioManager()

    def get_spaced_repetition_words(self, words: List[WordData], limit: int = 20) -> List[WordData]:
        review_words = [w for w in words if w.needs_review]
        review_words.sort(key=lambda w: w.mastery_level)
        return review_words[:limit]

    def update_word_mastery(self, word: WordData, correct: bool):
        word.review_count += 1
        word.last_reviewed = datetime.now()
        if correct:
            word.mastery_level = min(1.0, word.mastery_level + 0.2)
        else:
            word.mastery_level = max(0.0, word.mastery_level - 0.1)

    def calculate_streak(self, profile: UserProfile) -> int:
        if not profile.last_session:
            return 0
        last_date = profile.last_session.date()
        current_date = datetime.now().date()
        days_diff = (current_date - last_date).days
        if days_diff == 0:
            return profile.streak_days
        elif days_diff == 1:
            return profile.streak_days + 1
        else:
            return 0

# ============================================================================
# UI COMPONENTS
# ============================================================================
def load_css(dark_mode: bool = False):
    theme = {
        "bg": "#1a1a1a" if dark_mode else "#ffffff",
        "text": "#ffffff" if dark_mode else "#000000",
        "primary": "#6a11cb",
        "secondary": "#2575fc",
        "accent": "#ff6b6b",
        "success": "#51cf66",
        "warning": "#ffd43b",
        "card_bg": "#2d2d2d" if dark_mode else "#f8f9fa"
    }
    st.markdown(f"""
    <style>
    .stApp {{ background: {theme["bg"]}; color: {theme["text"]}; }}
    .current-word {{ background: linear-gradient(45deg, {theme["primary"]}, {theme["secondary"]}); color: white; padding: 20px; border-radius: 15px; font-size: 2.5rem; font-weight: bold; margin: 15px 0; display: inline-block; box-shadow: 0 6px 20px rgba(0,0,0,0.2); }}
    .word-button {{ font-size: 1.6rem; color: {theme["secondary"]}; padding: 15px; margin: 8px; border: 2px solid #ddd; border-radius: 12px; background: {theme["card_bg"]}; cursor: pointer; text-align: center; }}
    .word-button:hover {{ background: {theme["secondary"]}; color: white; }}
    .word-details {{ background: linear-gradient(135deg, {theme["primary"]} 0%, {theme["secondary"]} 100%); color: white; padding: 25px; border-radius: 20px; margin: 20px 0; text-align: center; box-shadow: 0 8px 30px rgba(0,0,0,0.15); }}
    .important-note {{ background: {theme["warning"]}; color: black; padding: 20px; border-radius: 15px; margin: 20px 0; border: 4px solid {theme["accent"]}; font-weight: bold; }}
    .mnemonic-box {{ background: linear-gradient(45deg, #ff9a9e, #fecfef); padding: 15px; border-radius: 10px; margin: 10px 0; border-left: 5px solid {theme["accent"]}; }}
    .progress-bar {{ height: 30px; background: {theme["card_bg"]}; border-radius: 15px; overflow: hidden; margin: 10px 0; }}
    .progress-fill {{ height: 100%; background: linear-gradient(90deg, {theme["success"]}, #20c997); transition: width 0.5s ease; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; }}
    .achievement-badge {{ background: linear-gradient(45deg, #ffd43b, #fab005); color: black; padding: 10px 20px; border-radius: 25px; display: inline-block; margin: 5px; font-weight: bold; }}
    .stats-card {{ background: {theme["card_bg"]}; padding: 20px; border-radius: 15px; margin: 10px 0; border: 2px solid {theme["secondary"]}; }}
    .flashcard {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 20px; margin: 20px 0; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.2); min-height: 300px; display: flex; flex-direction: column; justify-content: center; align-items: center; }}
    .quiz-question {{ background: #f8f9fa; padding: 25px; border-radius: 15px; margin: 15px 0; border-left: 5px solid {theme["primary"]}; }}
    .quiz-option {{ padding: 15px; margin: 10px 0; border-radius: 10px; border: 2px solid #ddd; cursor: pointer; transition: all 0.3s; }}
    .quiz-option:hover {{ background: {theme["primary"]}15; border-color: {theme["primary"]}; }}
    .quiz-option.correct {{ background: #d4edda; border-color: #28a745; }}
    .quiz-option.incorrect {{ background: #f8d7da; border-color: #dc3545; }}
    </style>
    """, unsafe_allow_html=True)

def render_word_details(word: WordData, audio_manager: AudioManager):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f'<div class="word-details">', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size: 3rem;">{word.image_hint} {word.english}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size: 2.5rem;">{word.hindi}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size: 1.5rem;">[{word.phonetic}]</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="mnemonic-box">', unsafe_allow_html=True)
        st.markdown(f"**💡 Memory Tip:** {word.mnemonic}")
        st.markdown('</div>', unsafe_allow_html=True)
        st.info(f"**Example:** {word.example_sentence}")
        st.markdown(f"**Mastery:** {int(word.mastery_level * 100)}%")
        st.markdown(f"""
        <div class="progress-bar">
            <div class="progress-fill" style="width: {word.mastery_level * 100}%">
                {int(word.mastery_level * 100)}%
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("### 🎧 Listen")
        audio_bytes = audio_manager.generate_audio(word.english)
        if audio_bytes:
            audio_manager.create_audio_player(audio_bytes, word.english, f"word_{word.english}")
        if word.example_sentence:
            st.markdown("**Sentence:**")
            sent_audio = audio_manager.generate_audio(word.example_sentence, slow=False)
            if sent_audio:
                audio_manager.create_audio_player(sent_audio, word.example_sentence, f"sentence_{word.example_sentence}")
        st.markdown("---")
        st.markdown("**Rate your knowledge:**")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("✅ I know this", key=f"know_{word.english}", use_container_width=True):
                return True
        with col_btn2:
            if st.button("❌ Need practice", key=f"dontknow_{word.english}", use_container_width=True):
                return False
    return None

def render_dashboard(profile: UserProfile, words: List[WordData]):
    st.markdown("## 📊 Your Learning Dashboard")
    learned = sum(1 for w in words if w.mastery_level >= 0.8)
    avg_mastery = sum(w.mastery_level for w in words) / len(words) if words else 0
    due_today = sum(1 for w in words if w.needs_review)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("🔥 Current Streak", f"{profile.streak_days} days")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("✅ Words Mastered", learned)
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("📈 Avg Mastery", f"{avg_mastery:.0%}")
        st.markdown('</div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("📝 Due for Review", due_today)
        st.markdown('</div>', unsafe_allow_html=True)
    achievements = []
    if profile.streak_days >= 7: achievements.append("🔥 Week Warrior")
    if profile.streak_days >= 30: achievements.append("📅 Monthly Master")
    if learned >= 50: achievements.append("🎯 Word Champion")
    if achievements:
        st.markdown("### 🏆 Achievements")
        for badge in achievements:
            st.markdown(f'<span class="achievement-badge">{badge}</span>', unsafe_allow_html=True)

# ============================================================================
# STORY LOADER
# ============================================================================
def load_all_story_files():
    stories = []
    json_files = glob.glob("story*.json") + glob.glob("*.json")
    unique_files = list(set(json_files))
    story_files = [f for f in unique_files if f not in ["progress.json", "stories.json"] and os.path.exists(f)]
    word_emojis = {word: emoji for word, emoji in {
        "I": "👤", "we": "👥", "you": "👉", "he": "👨", "she": "👩", "it": "🐾",
        "they": "👨‍👩‍👧‍👦", "this": "👇", "that": "👆", "these": "👇👇", "those": "👆👆",
        "my": "🎁", "your": "🎯", "his": "🎩", "her": "💍", "our": "🏠", "their": "🏘️",
        "the": "⭐", "a": "1️⃣", "an": "🔤",
        "am": "🟰", "is": "🟰", "are": "🟰", "was": "🕐", "were": "🕑",
        "have": "🤲", "has": "🖐️", "had": "🕰️",
        "do": "🔨", "does": "🔧", "did": "⏮️",
        "see": "👁️", "look": "👀", "watch": "📺",
        "like": "❤️", "love": "💖", "want": "🎯", "need": "❗",
        "play": "🎮", "run": "🏃", "jump": "🤸", "walk": "🚶",
        "eat": "🍎", "drink": "🥤", "sleep": "😴", "wake": "⏰",
        "cat": "🐱", "dog": "🐶", "bird": "🐦", "fish": "🐠", "ball": "⚽",
        "house": "🏠", "home": "🏡", "car": "🚗", "bus": "🚌", "book": "📚",
        "pen": "🖊️", "pencil": "✏️", "paper": "📄", "table": "🪑", "chair": "💺",
        "boy": "👦", "girl": "👧", "man": "👨", "woman": "👩", "child": "🧒",
        "happy": "😊", "sad": "😢", "big": "🐘", "small": "🐜", "tall": "🌳",
        "short": "📏", "red": "🔴", "blue": "🔵", "green": "🟢", "yellow": "🟡",
        "white": "⬜", "black": "⬛", "good": "👍", "bad": "👎", "hot": "🔥",
        "cold": "❄️", "new": "🆕", "old": "🕰️", "young": "👶", "fast": "⚡",
        "slow": "🐌", "clean": "✨", "dirty": "💩", "fluffy": "☁️", "round": "⭕",
        "and": "➕", "but": "🚫", "or": "🤔", "if": "❓", "because": "🔍",
        "in": "📦", "on": "🔼", "at": "📍", "to": "➡️", "from": "⬅️",
        "with": "🤝", "without": "🙅", "for": "🎁", "of": "🔗", "by": "👤",
        "up": "⬆️", "down": "⬇️", "here": "📍", "there": "🗺️", "now": "⏰",
        "then": "⏳", "always": "♾️", "never": "❌", "sometimes": "⏱️"
    }.items()}
    categories = {k: v for k, v in {
        "i": "pronoun", "we": "pronoun", "you": "pronoun", "he": "pronoun",
        "she": "pronoun", "it": "pronoun", "they": "pronoun", "this": "pronoun",
        "that": "pronoun", "these": "pronoun", "those": "pronoun", "my": "pronoun",
        "your": "pronoun", "his": "pronoun", "her": "pronoun", "our": "pronoun",
        "their": "pronoun",
        "the": "article", "a": "article", "an": "article",
        "am": "verb", "is": "verb", "are": "verb", "was": "verb", "were": "verb",
        "have": "verb", "has": "verb", "had": "verb", "do": "verb", "does": "verb",
        "did": "verb", "see": "verb", "look": "verb", "watch": "verb", "like": "verb",
        "love": "verb", "want": "verb", "need": "verb", "play": "verb", "run": "verb",
        "jump": "verb", "walk": "verb", "eat": "verb", "drink": "verb", "sleep": "verb",
        "wake": "verb",
        "cat": "noun", "dog": "noun", "bird": "noun", "fish": "noun", "ball": "noun",
        "house": "noun", "home": "noun", "car": "noun", "bus": "noun", "book": "noun",
        "pen": "noun", "pencil": "noun", "paper": "noun", "table": "noun", "chair": "noun",
        "boy": "noun", "girl": "noun", "man": "noun", "woman": "noun", "child": "noun",
        "happy": "adjective", "sad": "adjective", "big": "adjective", "small": "adjective",
        "tall": "adjective", "short": "adjective", "red": "adjective", "blue": "adjective",
        "green": "adjective", "yellow": "adjective", "white": "adjective", "black": "adjective",
        "good": "adjective", "bad": "adjective", "hot": "adjective", "cold": "adjective",
        "new": "adjective", "old": "adjective", "young": "adjective", "fast": "adjective",
        "slow": "adjective", "clean": "adjective", "dirty": "adjective", "fluffy": "adjective",
        "round": "adjective",
        "in": "preposition", "on": "preposition", "at": "preposition", "to": "preposition",
        "from": "preposition", "with": "preposition", "without": "preposition", "for": "preposition",
        "of": "preposition", "by": "preposition", "up": "preposition", "down": "preposition",
        "and": "conjunction", "but": "conjunction", "or": "conjunction", "if": "conjunction",
        "because": "conjunction"
    }.items()}
    for story_file in sorted(story_files):
        try:
            with open(story_file, 'r', encoding='utf-8') as f:
                story_data = json.load(f)
            word_objects = []
            for word_dict in story_data.get("content", []):
                english_word = word_dict.get("english", "")
                if not english_word: continue
                emoji = word_emojis.get(english_word.lower(), "📝")
                category = categories.get(english_word.lower(), "general")
                if category == "pronoun": example = f"{english_word} am learning English."
                elif category == "verb": example = f"I {english_word} every day."
                elif category == "noun": example = f"This is a {english_word}."
                elif category == "adjective": example = f"The {english_word} cat."
                elif category == "article": example = f"{english_word} book is interesting."
                else: example = f"This is the word '{english_word}'"
                mnemonic = f"Remember: '{english_word}' means '{word_dict.get('hindi', '')}'"
                level = story_data.get("level", "Beginner")
                difficulty = 1 if level == "Beginner" else 2 if level == "Intermediate" else 3
                word_obj = WordData(
                    english=english_word,
                    hindi=word_dict.get("hindi", ""),
                    phonetic=word_dict.get("phonetic", "/?/"),
                    category=category,
                    difficulty=difficulty,
                    example_sentence=example,
                    mnemonic=mnemonic,
                    image_hint=emoji
                )
                word_objects.append(word_obj)
            story = {
                "title": story_data.get("title", f"Story"),
                "hindi_title": story_data.get("hindi_title", "कहानी"),
                "difficulty": difficulty,
                "level": level,
                "filename": story_file,
                "content": word_objects
            }
            stories.append(story)
        except Exception as e:
            st.sidebar.warning(f"Could not load {story_file}: {str(e)}")
    return stories

# ============================================================================
# FLASHCARDS (10)
# ============================================================================
def render_flashcards(review_words: List[WordData], audio_manager: AudioManager, engine: LearningEngine):
    if 'flashcard_session' not in st.session_state:
        st.session_state.flashcard_session = {'words': review_words[:10], 'current_index': 0, 'show_answer': False, 'completed': []}
    session = st.session_state.flashcard_session
    if not session['words']:
        st.success("🎉 All flashcards completed!")
        if st.button("Start New Session"): del st.session_state.flashcard_session; st.rerun()
        return
    current_word = session['words'][session['current_index']]
    total_cards = len(session['words'])
    current_card = session['current_index'] + 1
    st.progress(current_card / total_cards)
    st.caption(f"Card {current_card} of {total_cards}")
    st.markdown(f"""
    <div class="flashcard">
        <h1 style="font-size: 4rem;">{current_word.english}</h1>
        <h2 style="font-size: 3rem;">{current_word.image_hint}</h2>
    </div>
    """, unsafe_allow_html=True)
    audio_bytes = audio_manager.generate_audio(current_word.english)
    if audio_bytes:
        audio_manager.create_audio_player(audio_bytes, current_word.english, f"flashcard_{current_card}")
    if not session['show_answer']:
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🃏 Show Answer", type="primary", use_container_width=True):
                session['show_answer'] = True
                st.rerun()
        with col2:
            if st.button("⏭️ Skip Card", use_container_width=True):
                session['completed'].append((current_word, False))
                session['current_index'] += 1
                session['show_answer'] = False
                if session['current_index'] >= len(session['words']):
                    show_flashcard_results(session['completed'], engine)
                else:
                    st.rerun()
    else:
        st.markdown(f"""
        <div style="background: white; padding: 30px; border-radius: 15px; margin: 20px 0; text-align: center;">
            <h2 style="color: #ff6b6b; font-size: 3rem;">{current_word.hindi}</h2>
            <p style="font-size: 1.5rem; color: #666;">{current_word.phonetic}</p>
            <p style="font-size: 1.2rem; color: #888;">Category: {current_word.category}</p>
        </div>
        """, unsafe_allow_html=True)
        if current_word.example_sentence:
            st.info(f"**Example:** {current_word.example_sentence}")
            sent_audio = audio_manager.generate_audio(current_word.example_sentence)
            if sent_audio:
                audio_manager.create_audio_player(sent_audio, current_word.example_sentence, f"flashcard_sent_{current_card}")
        st.markdown(f"**💡 Tip:** {current_word.mnemonic}")
        st.markdown("### How well did you know this word?")
        col1, col2, col3, col4 = st.columns(4)
        def advance(correct: bool):
            engine.update_word_mastery(current_word, correct)
            session['completed'].append((current_word, correct))
            session['current_index'] += 1
            session['show_answer'] = False
            if session['current_index'] >= len(session['words']):
                show_flashcard_results(session['completed'], engine)
            else:
                st.rerun()
        with col1:
            if st.button("✅ Easy", use_container_width=True, key=f"easy_{current_word.english}"): advance(True)
        with col2:
            if st.button("🟡 Medium", use_container_width=True, key=f"medium_{current_word.english}"): advance(True)
        with col3:
            if st.button("❌ Hard", use_container_width=True, key=f"hard_{current_word.english}"): advance(False)
        with col4:
            if st.button("⏭️ Next", use_container_width=True, key=f"next_{current_word.english}"): advance(False)

def show_flashcard_results(completed: List[Tuple[WordData, bool]], engine: LearningEngine):
    correct = sum(1 for _, correct in completed if correct)
    total = len(completed)
    score = (correct / total) * 100 if total > 0 else 0
    st.success(f"🎉 Session Complete!")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Score", f"{score:.0f}%")
    with col2: st.metric("Correct", correct)
    with col3: st.metric("Total", total)
    with st.expander("📊 View Details"):
        for word, was_correct in completed:
            emoji = "✅" if was_correct else "❌"
            mastery_emoji = word.get_mastery_badge()
            st.write(f"{emoji} {mastery_emoji} **{word.english}** = {word.hindi} ({int(word.mastery_level * 100)}%)")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Practice Again", use_container_width=True):
            del st.session_state.flashcard_session
            st.rerun()
    with col2:
        if st.button("📚 Back to Learning", use_container_width=True):
            del st.session_state.flashcard_session
            st.rerun()

# ============================================================================
# QUIZ (10)
# ============================================================================
def render_quiz_session(review_words: List[WordData], audio_manager: AudioManager, engine: LearningEngine):
    if 'quiz_session' not in st.session_state:
        st.session_state.quiz_session = {'questions': generate_quiz_questions(review_words, num_questions=10), 'current_index': 0, 'answers': [], 'completed': False}
    session = st.session_state.quiz_session
    if not session['questions']:
        st.info("Not enough words for a quiz. Learn more words first!")
        return
    if session['completed']:
        show_quiz_results(session['questions'], session['answers'], engine)
        return
    question = session['questions'][session['current_index']]
    total_questions = len(session['questions'])
    current_q = session['current_index'] + 1
    st.progress(current_q / total_questions)
    st.caption(f"Question {current_q} of {total_questions}")
    st.markdown(f"""
    <div class="quiz-question">
        <h3>What is the Hindi translation of:</h3>
        <h2 style="font-size: 2.5rem; color: #6a11cb;">"{question['word'].english}"</h2>
    </div>
    """, unsafe_allow_html=True)
    audio_bytes = audio_manager.generate_audio(question['word'].english)
    if audio_bytes:
        audio_manager.create_audio_player(audio_bytes, question['word'].english, f"quiz_{current_q}")
    selected_option = st.radio("Choose the correct translation:", question['options'], key=f"quiz_option_{session['current_index']}")
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Submit Answer", type="primary", use_container_width=True):
            is_correct = selected_option == question['correct']
            session['answers'].append({'word': question['word'], 'selected': selected_option, 'correct': question['correct'], 'is_correct': is_correct})
            engine.update_word_mastery(question['word'], is_correct)
            session['current_index'] += 1
            if session['current_index'] >= len(session['questions']): session['completed'] = True
            st.rerun()
    with col2:
        if st.button("Skip Question", use_container_width=True):
            session['answers'].append({'word': question['word'], 'selected': "Skipped", 'correct': question['correct'], 'is_correct': False})
            session['current_index'] += 1
            if session['current_index'] >= len(session['questions']): session['completed'] = True
            st.rerun()

def generate_quiz_questions(words: List[WordData], num_questions: int = 10) -> List[Dict]:
    if len(words) < 4: return []
    questions = []
    used_words = set()
    for _ in range(min(num_questions, len(words))):
        available_words = [w for w in words if w.english not in used_words]
        if not available_words: break
        word = random.choice(available_words)
        used_words.add(word.english)
        correct = word.hindi
        wrong_pool = [w.hindi for w in words if w.hindi != correct]
        if len(wrong_pool) < 3: wrong_options = ["गलत", "अनुवाद", "शब्द"][:3]
        else: wrong_options = random.sample(wrong_pool, 3)
        options = [correct] + wrong_options
        random.shuffle(options)
        questions.append({'word': word, 'correct': correct, 'options': options})
    return questions

def show_quiz_results(questions: List[Dict], answers: List[Dict], engine: LearningEngine):
    correct_count = sum(1 for answer in answers if answer['is_correct'])
    total = len(questions)
    score = (correct_count / total) * 100 if total > 0 else 0
    st.success("🎉 Quiz Complete!")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Score", f"{score:.0f}%")
    with col2: st.metric("Correct", correct_count)
    with col3: st.metric("Total", total)
    rating = "🏆 Excellent!" if score >= 90 else "👍 Good job!" if score >= 70 else "😊 Not bad!" if score >= 50 else "💪 Keep practicing!"
    st.info(rating)
    with st.expander("📋 Review Answers"):
        for i, (question, answer) in enumerate(zip(questions, answers), 1):
            emoji = "✅" if answer['is_correct'] else "❌"
            st.markdown(f"**Q{i}: {question['word'].english}**")
            st.markdown(f"{emoji} Your answer: **{answer['selected']}**" + (" (Correct!)" if answer['is_correct'] else ""))
            st.markdown(f"Correct answer: **{answer['correct']}**")
            audio_bytes = engine.audio_manager.generate_audio(question['word'].english)
            if audio_bytes:
                engine.audio_manager.create_audio_player(audio_bytes, question['word'].english, f"review_{i}")
            st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Try Again", use_container_width=True):
            del st.session_state.quiz_session
            st.rerun()
    with col2:
        if st.button("📚 Back to Learning", use_container_width=True):
            del st.session_state.quiz_session
            st.rerun()

# ============================================================================
# MAIN APPLICATION
# ============================================================================
def main():
    storage = LearningStorage()
    audio_manager = AudioManager()
    engine = LearningEngine()
    dark_mode = st.session_state.get('profile', UserProfile(name="Learner")).dark_mode
    load_css(dark_mode)
    st.title("📚 Bilingual English Master")
    st.markdown("**Learn English through Hindi | Intelligent & Adaptive**")
    
    with st.sidebar:
        if 'profile' not in st.session_state:
            profile, _ = storage.load_progress()
            if not profile: profile = UserProfile(name="Learner")
            st.session_state.profile = profile
        new_name = st.text_input("Your Name", st.session_state.profile.name)
        if new_name != st.session_state.profile.name:
            st.session_state.profile.name = new_name
            st.success(f"Welcome, {new_name}!")
        st.session_state.profile.auto_play_audio = st.checkbox("Auto-play audio", st.session_state.profile.auto_play_audio)
        st.session_state.profile.dark_mode = st.checkbox("Dark Mode", st.session_state.profile.dark_mode)
        pace = st.select_slider("Learning Pace", options=["slow", "normal", "fast"], value=st.session_state.profile.learning_pace)
        st.session_state.profile.learning_pace = pace
        if st.button("🗑️ Clear Audio Cache"):
            audio_manager.clear_cache()

    current_stories = load_all_story_files()
    if 'stories' not in st.session_state:
        st.session_state.stories = current_stories
    else:
        current_filenames = {s['filename'] for s in current_stories}
        existing_filenames = {s.get('filename', '') for s in st.session_state.stories}
        if current_filenames != existing_filenames:
            st.session_state.stories = current_stories

    if not st.session_state.stories:
        st.error("⚠️ No story files found! Please add JSON story files.")
        return

    if 'all_words' not in st.session_state:
        all_words = []
        for story in st.session_state.stories:
            all_words.extend(story['content'])
        _, saved_words = storage.load_progress()
        if saved_words:
            word_dict = {w.english: w for w in saved_words}
            for word in all_words:
                if word.english in word_dict:
                    saved = word_dict[word.english]
                    word.mastery_level = saved.mastery_level
                    word.review_count = saved.review_count
                    word.last_reviewed = saved.last_reviewed
        st.session_state.all_words = all_words

    render_dashboard(st.session_state.profile, st.session_state.all_words)
    total_stories = len(st.session_state.stories)
    total_words = len(st.session_state.all_words)
    unique_words = len(set(word.english for word in st.session_state.all_words))
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("📚 Total Stories", total_stories)
    with col2: st.metric("📝 Total Words", total_words)
    with col3: st.metric("✨ Unique Words", unique_words)

    st.markdown("""
    <div class="important-note">
        🔊 <strong>Audio now plays cleanly without overlapping or loop buttons.</strong><br>
        Each word plays only one audio at a time. No more desynchronization!
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🎵 Step 1: Test Your Audio")
    if st.button("🔊 TEST AUDIO - Click First!", key="test_audio", type="primary", use_container_width=True):
        st.session_state.test_audio_triggered = True
    if st.session_state.get('test_audio_triggered', False):
        test_audio = audio_manager.generate_audio("Hello! Your audio is working perfectly!")
        if test_audio:
            audio_manager.create_audio_player(test_audio, "Test Audio", "test_audio_player")
        st.success("✅ Audio is ready! Play it without interference.")

    st.markdown("---")
    story_options = {}
    for i, s in enumerate(st.session_state.stories):
        level_emoji = "🟢" if s.get('difficulty', 1) == 1 else "🟡" if s.get('difficulty', 1) == 2 else "🔴"
        story_options[f"{level_emoji} {s['title']} ({s['hindi_title']}) - {len(s['content'])} words"] = i

    selected_story = st.selectbox("Choose a story:", options=list(story_options.keys()), index=st.session_state.get('current_story', 0))
    story_idx = story_options[selected_story]
    st.session_state.current_story = story_idx
    story = st.session_state.stories[story_idx]

    st.markdown(f"## 📖 {story['title']} - {story['hindi_title']}")
    st.markdown(f"**Level:** {story.get('level', 'Beginner')} | **Words:** {len(story['content'])} | **Source:** `{story.get('filename', 'Unknown')}`")

    st.markdown("### 📖 Complete Story:")
    story_text_english = " ".join([word.english for word in story['content']])
    story_text_hindi = " ".join([word.hindi for word in story['content']])
    col1, col2 = st.columns(2)
    with col1: st.markdown(f"**English:** {story_text_english}")
    with col2: st.markdown(f"**Hindi:** {story_text_hindi}")

    if st.button("🎧 Listen to Full Story"):
        full_audio = audio_manager.generate_audio(story_text_english)
        if full_audio:
            audio_manager.create_audio_player(full_audio, story_text_english, "full_story")

    st.markdown("---")
    st.markdown("### 🎯 Click any word to learn:")
cols_per_row = 4
words = story['content']
for global_idx in range(0, len(words), cols_per_row):
    row = words[global_idx : global_idx + cols_per_row]
    cols = st.columns(len(row))
    for col_offset, word_data in enumerate(row):
        with cols[col_offset]:
            # Ensure word text is never empty
            display_word = word_data.english.strip()
            if not display_word:
                display_word = "❓"
            badge = word_data.get_mastery_badge()
            unique_key = f"word_{story_idx}_{global_idx + col_offset}_{display_word}"
            # Mobile-safe button: force text to show
            button_label = f"{badge} {display_word}"
            if st.button(
                button_label,
                key=unique_key,
                use_container_width=True,
                help=f"{word_data.hindi} - {int(word_data.mastery_level * 100)}% mastered"
            ):
                st.session_state.current_word = word_data
                st.rerun()

    if 'current_word' in st.session_state and st.session_state.current_word:
        word = st.session_state.current_word
        st.markdown("---")
        feedback = render_word_details(word, audio_manager)
        if feedback is not None:
            engine.update_word_mastery(word, feedback)
            storage.save_progress(st.session_state.profile, st.session_state.all_words)
            st.success("Progress saved!")
            time.sleep(0.5)
            st.rerun()

    st.markdown("---")
    st.markdown("### 🧠 Smart Review (Spaced Repetition)")
    review_words = engine.get_spaced_repetition_words(st.session_state.all_words, limit=20)
    if review_words:
        st.info(f"📚 {len(review_words)} words due for review!")
        review_mode = st.radio("Choose review mode:", ["Flashcards (10 cards per session)", "Quiz (10 questions per session)"], horizontal=True)
        if review_mode.startswith("Flashcards"):
            render_flashcards(review_words, audio_manager, engine)
        else:
            render_quiz_session(review_words, audio_manager, engine)
    else:
        st.success("🎉 No words due for review! Keep learning new words.")

    st.markdown("---")
    with st.expander("📚 Browse All Words"):
        search = st.text_input("Search words...")
        filtered_words = [w for w in st.session_state.all_words if not search or search.lower() in w.english.lower() or search.lower() in w.hindi.lower()]
        for i, word in enumerate(sorted(filtered_words, key=lambda w: w.english)):
            col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
            with col1: st.markdown(f"**{word.english}** {word.image_hint}")
            with col2: st.markdown(f"*{word.hindi}*")
            with col3: st.markdown(f"{int(word.mastery_level * 100)}%")
            with col4:
                audio_bytes = audio_manager.generate_audio(word.english)
                if audio_bytes:
                    audio_manager.create_audio_player(audio_bytes, word.english, f"browse_{i}")

    st.markdown("---")
    if st.button("💾 Save All Progress", use_container_width=True):
        storage.save_progress(st.session_state.profile, st.session_state.all_words)
        st.success("✅ Progress saved successfully!")
        st.session_state.profile.last_session = datetime.now()
        st.session_state.profile.streak_days = engine.calculate_streak(st.session_state.profile)

if __name__ == "__main__":
    main()


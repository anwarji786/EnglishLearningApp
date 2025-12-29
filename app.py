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
# STORY LOADER - FIXED VERSION
# ============================================================================

def load_stories_from_files():
    """Load stories from JSON files with DEBUGGING."""
    stories = []
    
    # DEBUG: Show all files in directory
    all_files = os.listdir(".")
    print("=== FILES IN DIRECTORY ===")
    for f in all_files:
        print(f"  - {f}")
    
    # Look for JSON files
    json_files = glob.glob("*.json")
    print(f"\n=== JSON FILES FOUND ===")
    print(f"Found {len(json_files)} JSON files: {json_files}")
    
    # Filter out system files
    json_files = [f for f in json_files 
                  if os.path.basename(f) not in ["user_data.json", "requirements.txt"]]
    
    print(f"\n=== PROCESSING JSON FILES ===")
    
    for file_path in json_files:
        print(f"\nProcessing: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"  File loaded successfully")
            print(f"  Data type: {type(data)}")
            
            word_list = []
            
            # Determine content structure
            content_items = []
            
            if isinstance(data, list):
                print(f"  Data is a list with {len(data)} items")
                content_items = data
            elif isinstance(data, dict):
                print(f"  Data is a dict with keys: {list(data.keys())}")
                
                # Try to find content
                content_key = None
                for key in ["content", "words", "vocabulary", "data", "items", "story"]:
                    if key in data:
                        content_key = key
                        break
                
                if content_key:
                    print(f"  Found content in key: '{content_key}'")
                    content = data[content_key]
                    if isinstance(content, list):
                        content_items = content
                    else:
                        print(f"  Warning: '{content_key}' is not a list, it's {type(content)}")
                else:
                    print(f"  Warning: No content key found in dict")
                    # Try to use the dict itself as a word
                    content_items = [data]
            
            print(f"  Content items to process: {len(content_items)}")
            
            # Process each item
            for i, item in enumerate(content_items[:5]):  # Only show first 5 for debugging
                print(f"\n  Item {i}:")
                print(f"    Type: {type(item)}")
                
                if isinstance(item, dict):
                    print(f"    Keys: {list(item.keys())}")
                    
                    # Find the English word - be very specific
                    english = None
                    
                    # Look for English word in specific keys
                    english_keys = ["english", "English", "word", "Word", "text", "en", "name"]
                    for key in english_keys:
                        if key in item:
                            value = item[key]
                            print(f"    Found '{key}': '{value}' (type: {type(value)})")
                            if isinstance(value, str) and value.strip():
                                english = value.strip()
                                break
                    
                    if english:
                        print(f"    ✓ Using English word: '{english}'")
                        
                        # Get Hindi translation
                        hindi = ""
                        hindi_keys = ["hindi", "Hindi", "translation", "Translation", "meaning", "Meaning", "hi"]
                        for key in hindi_keys:
                            if key in item and item[key]:
                                hindi = str(item[key]).strip()
                                break
                        
                        if not hindi:
                            hindi = f"Translation for {english}"
                        
                        # Get other fields
                        phonetic = item.get("phonetic", item.get("pronunciation", f"/{english.lower()}/"))
                        category = item.get("category", item.get("type", "general"))
                        difficulty = item.get("difficulty", 1)
                        example_sentence = item.get("example_sentence", item.get("example", f"This is {english}."))
                        mnemonic = item.get("mnemonic", item.get("tip", f"Remember {english}"))
                        
                        # Get emoji
                        image_hint = "📝"
                        emoji_keys = ["image_hint", "emoji", "icon", "symbol", "image"]
                        for key in emoji_keys:
                            if key in item and item[key]:
                                image_hint = str(item[key])
                                break
                        
                        # Create word object
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
                        print(f"    ✓ Added word: {english} → {hindi}")
                    else:
                        print(f"    ✗ No English word found in this item")
                else:
                    print(f"    ✗ Item is not a dict, skipping")
            
            print(f"\n  Total words created: {len(word_list)}")
            
            if word_list:
                # Get title
                title = "Unknown Story"
                if isinstance(data, dict) and "title" in data:
                    title = data["title"]
                else:
                    title = os.path.basename(file_path).replace(".json", "").replace("_", " ").title()
                
                stories.append({
                    "filename": file_path,
                    "title": f"{title} ({len(word_list)} words)",
                    "content": word_list
                })
                print(f"  ✓ Story added: {title} with {len(word_list)} words")
            else:
                print(f"  ✗ No valid words found in {file_path}")
                
        except Exception as e:
            print(f"  ✗ ERROR loading {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # If no stories loaded, create test data
    if not stories:
        print("\n=== NO STORIES LOADED, CREATING TEST DATA ===")
        test_data = [
            {"english": "Hello", "hindi": "नमस्ते", "emoji": "👋"},
            {"english": "Goodbye", "hindi": "अलविदा", "emoji": "👋"},
            {"english": "Thank you", "hindi": "धन्यवाद", "emoji": "🙏"},
            {"english": "Please", "hindi": "कृपया", "emoji": "🙏"},
            {"english": "Water", "hindi": "पानी", "emoji": "💧"},
        ]
        
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
            "title": "Test Words (5 words)",
            "content": word_list
        })
        print("✓ Created test data with 5 words")
    
    print(f"\n=== LOADING COMPLETE ===")
    print(f"Total stories loaded: {len(stories)}")
    for i, story in enumerate(stories):
        print(f"  {i}. {story['title']}")
        if story['content']:
            print(f"     First 3 words: {[w.english for w in story['content'][:3]]}")
    
    return stories

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(page_title="Bilingual Master", layout="wide")
    
    # Clear session state on first run
    if 'app_started' not in st.session_state:
        st.session_state.app_started = True
        keys_to_clear = ['learn_index', 'show_meaning', 'flashcard_index', 
                        'flashcard_show', 'quiz_index', 'quiz_score', 'quiz_questions']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    # Initialize managers
    storage = StorageManager()
    audio_mgr = AudioManager()
    profile, saved_words = storage.load()
    
    # CSS
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
    with st.spinner("Loading stories..."):
        stories = load_stories_from_files()
    
    # Display debug info in sidebar
    with st.sidebar:
        st.header("Debug Info")
        st.write(f"Stories loaded: {len(stories)}")
        
        if stories:
            st.write("Available stories:")
            for i, story in enumerate(stories):
                st.write(f"{i}. {story['title']}")
                if story['content']:
                    st.write(f"   Words: {len(story['content'])}")
                    if len(story['content']) > 0:
                        st.write(f"   Sample: {story['content'][0].english if hasattr(story['content'][0], 'english') else 'No english attr'}")
    
    # Title
    st.title("📚 Bilingual Master")
    
    # If no stories, show error
    if not stories:
        st.error("No stories loaded. Check the console for debugging information.")
        return
    
    # Story selection in main area (not sidebar)
    st.subheader("Select a Story")
    story_titles = [s['title'] for s in stories]
    selected_idx = st.selectbox("Choose:", range(len(stories)), format_func=lambda i: story_titles[i])
    
    current_story = stories[selected_idx]
    current_words = current_story['content']
    
    # Debug: Show what words were loaded
    with st.expander("Debug: Show loaded words"):
        if current_words:
            st.write(f"Total words: {len(current_words)}")
            for i, word in enumerate(current_words):
                st.write(f"{i+1}. English: '{word.english}', Hindi: '{word.hindi}'")
        else:
            st.write("No words loaded")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📖 Learn", "🎴 Review", "🧠 Quiz"])
    
    # TAB 1: LEARN
    with tab1:
        if current_words:
            st.markdown(f"### Learning: {current_story['title']}")
            
            # Initialize session state
            if 'learn_index' not in st.session_state:
                st.session_state.learn_index = 0
            if 'show_meaning' not in st.session_state:
                st.session_state.show_meaning = False
            
            idx = st.session_state.learn_index
            if idx >= len(current_words):
                idx = 0
                st.session_state.learn_index = 0
            
            word = current_words[idx]
            
            # Navigation
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.button("⬅️ Previous", disabled=(idx == 0), key=f"prev_{idx}"):
                    st.session_state.learn_index -= 1
                    st.session_state.show_meaning = False
                    st.rerun()
            
            with col3:
                if st.button("Next ➡️", disabled=(idx == len(current_words)-1), key=f"next_{idx}"):
                    st.session_state.learn_index += 1
                    st.session_state.show_meaning = False
                    st.rerun()
            
            with col2:
                st.progress((idx + 1) / len(current_words))
                st.caption(f"Word {idx + 1} of {len(current_words)}")
            
            # Display the word
            st.markdown(f"""
            <div class="word-card">
                <div style="font-size: 4rem;">{word.image_hint}</div>
                <div class="english-word">{word.english}</div>
                <div style="font-size: 1.2rem; opacity: 0.7;">{word.phonetic}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show word in text for debugging
            st.write(f"Debug - Current word: '{word.english}' (type: {type(word.english)})")
            
            # Audio
            audio_bytes = audio_mgr.get_audio_bytes(word.english, slow=True)
            if audio_bytes:
                b64_audio = base64.b64encode(audio_bytes).decode()
                st.markdown(f"""
                <div style="margin: 20px 0;">
                    <audio controls style="width: 100%;">
                        <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mpeg">
                    </audio>
                </div>
                """, unsafe_allow_html=True)
            
            # Show meaning button
            if st.button("Show Meaning", key=f"show_{idx}"):
                st.session_state.show_meaning = not st.session_state.show_meaning
                st.rerun()
            
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
        else:
            st.warning("No words available in this story.")
    
    # TAB 2: REVIEW
    with tab2:
        if current_words:
            st.markdown("### Review Flashcards")
            
            if 'flashcard_index' not in st.session_state:
                st.session_state.flashcard_index = 0
                st.session_state.flashcard_show = False
            
            idx = st.session_state.flashcard_index % len(current_words)
            word = current_words[idx]
            
            # Flashcard
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"""
                <div class="word-card" style="min-height: 300px;">
                    <div class="english-word">{word.english}</div>
                    <div style="font-size: 3rem;">{word.image_hint}</div>
                    {f'<div class="hindi-word">{word.hindi}</div>' if st.session_state.flashcard_show else ''}
                </div>
                """, unsafe_allow_html=True)
            
            # Controls
            if not st.session_state.flashcard_show:
                if st.button("Show Answer", key="fc_show"):
                    st.session_state.flashcard_show = True
                    st.rerun()
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("❌ Hard", key="fc_hard"):
                        st.session_state.flashcard_index += 1
                        st.session_state.flashcard_show = False
                        st.rerun()
                with col2:
                    if st.button("🟡 Good", key="fc_good"):
                        st.session_state.flashcard_index += 1
                        st.session_state.flashcard_show = False
                        st.rerun()
                with col3:
                    if st.button("✅ Easy", key="fc_easy"):
                        st.session_state.flashcard_index += 1
                        st.session_state.flashcard_show = False
                        st.rerun()
    
    # TAB 3: QUIZ
    with tab3:
        if len(current_words) >= 4:
            st.markdown("### Quiz")
            
            if 'quiz_index' not in st.session_state:
                st.session_state.quiz_index = 0
                st.session_state.quiz_score = 0
                st.session_state.quiz_questions = random.sample(current_words, min(5, len(current_words)))
            
            if st.session_state.quiz_index >= len(st.session_state.quiz_questions):
                st.success(f"Score: {st.session_state.quiz_score}/{len(st.session_state.quiz_questions)}")
                if st.button("New Quiz"):
                    st.session_state.quiz_index = 0
                    st.session_state.quiz_score = 0
                    st.session_state.quiz_questions = random.sample(current_words, min(5, len(current_words)))
                    st.rerun()
            else:
                word = st.session_state.quiz_questions[st.session_state.quiz_index]
                
                st.markdown(f"**Question {st.session_state.quiz_index + 1}**")
                st.markdown(f"### {word.english}")
                
                # Options
                options = [word.hindi]
                other_words = [w for w in current_words if w != word]
                options.extend(random.sample([w.hindi for w in other_words], 3))
                random.shuffle(options)
                
                selected = st.radio("Choose meaning:", options, key=f"q_{st.session_state.quiz_index}")
                
                if st.button("Submit", key=f"s_{st.session_state.quiz_index}"):
                    if selected == word.hindi:
                        st.session_state.quiz_score += 1
                    st.session_state.quiz_index += 1
                    st.rerun()

if __name__ == "__main__":
    main()

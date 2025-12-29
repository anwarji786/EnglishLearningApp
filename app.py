import streamlit as st
import json
import os
import random
from pathlib import Path

# Clear session state
for key in list(st.session_state.keys()):
    if key != 'app_started':
        del st.session_state[key]

st.set_page_config(page_title="Language Learner", layout="wide")

# First, let's debug what files are there
st.sidebar.title("Debug Information")

# List all files
files = os.listdir(".")
st.sidebar.write("Files in directory:")
for f in files:
    st.sidebar.write(f"- {f}")

# Look for JSON files
json_files = [f for f in files if f.endswith('.json') and f not in ['user_data.json', 'requirements.txt']]
st.sidebar.write(f"\nJSON files found: {len(json_files)}")

# Load and display the content of each JSON file
all_words = []

for json_file in json_files:
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)
        
        st.sidebar.write(f"\n=== {json_file} ===")
        st.sidebar.write(f"Type: {type(data)}")
        
        if isinstance(data, dict):
            st.sidebar.write(f"Keys: {list(data.keys())}")
            
            # Try to find words in different possible structures
            words_data = None
            for key in ['content', 'words', 'data', 'vocabulary', 'items']:
                if key in data:
                    words_data = data[key]
                    st.sidebar.write(f"Found words in key: '{key}'")
                    break
            
            if words_data and isinstance(words_data, list):
                for i, item in enumerate(words_data[:3]):  # Show first 3 items
                    st.sidebar.write(f"  Item {i}: {item}")
                    if isinstance(item, dict):
                        # Try to extract English word
                        english = None
                        for eng_key in ['english', 'English', 'word', 'Word', 'en', 'text']:
                            if eng_key in item:
                                english = item[eng_key]
                                all_words.append(english)
                                break
        
        elif isinstance(data, list):
            st.sidebar.write(f"List with {len(data)} items")
            for i, item in enumerate(data[:3]):  # Show first 3 items
                st.sidebar.write(f"  Item {i}: {item}")
                if isinstance(item, dict):
                    # Try to extract English word
                    english = None
                    for eng_key in ['english', 'English', 'word', 'Word', 'en', 'text']:
                        if eng_key in item:
                            english = item[eng_key]
                            all_words.append(english)
                            break
                            
    except Exception as e:
        st.sidebar.write(f"Error reading {json_file}: {e}")

# Now create the main app
st.title("📚 Language Learner")

# If we found words in JSON files, use them. Otherwise use default words
if all_words:
    words = list(set(all_words))[:20]  # Remove duplicates, take first 20
    st.success(f"Loaded {len(words)} words from JSON files")
else:
    # Default words if no JSON files or no words found
    words = ["Hello", "Goodbye", "Thank you", "Please", "Sorry", "Yes", "No", 
             "Water", "Food", "Friend", "House", "Book", "School", "Teacher", 
             "Student", "Mother", "Father", "Sister", "Brother", "Family"]
    st.warning("Using default words (no valid words found in JSON files)")

# Initialize session state
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'show_hindi' not in st.session_state:
    st.session_state.show_hindi = False

# Get current index
idx = st.session_state.current_index
if idx >= len(words):
    idx = 0
    st.session_state.current_index = 0

current_word = words[idx]

# Navigation
col1, col2, col3 = st.columns([1, 3, 1])

with col1:
    if st.button("⬅️ Previous", disabled=(idx == 0)):
        st.session_state.current_index -= 1
        st.session_state.show_hindi = False
        st.rerun()

with col3:
    if st.button("Next ➡️", disabled=(idx == len(words)-1)):
        st.session_state.current_index += 1
        st.session_state.show_hindi = False
        st.rerun()

with col2:
    st.progress((idx + 1) / len(words))
    st.caption(f"Word {idx + 1} of {len(words)}")

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
        {current_word[0].upper()}  <!-- First letter as emoji substitute -->
    </div>
    <div style="font-size: 5rem; font-weight: bold; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
        {current_word}
    </div>
    <div style="font-size: 1.5rem; opacity: 0.9;">
        /{current_word.lower().replace(' ', '_')}/
    </div>
</div>
""", unsafe_allow_html=True)

# Show/Hide meaning button
if st.button("🔍 Show/Hide Meaning", type="secondary", use_container_width=True):
    st.session_state.show_hindi = not st.session_state.show_hindi
    st.rerun()

# Show meaning if toggled
if st.session_state.show_hindi:
    # Simple Hindi translation lookup
    hindi_dict = {
        "Hello": "नमस्ते",
        "Goodbye": "अलविदा", 
        "Thank you": "धन्यवाद",
        "Please": "कृपया",
        "Sorry": "माफ कीजिए",
        "Yes": "हाँ",
        "No": "नहीं",
        "Water": "पानी",
        "Food": "भोजन",
        "Friend": "दोस्त",
        "House": "घर",
        "Book": "किताब",
        "School": "स्कूल",
        "Teacher": "शिक्षक",
        "Student": "छात्र",
        "Mother": "माँ",
        "Father": "पिता",
        "Sister": "बहन",
        "Brother": "भाई",
        "Family": "परिवार"
    }
    
    hindi_word = hindi_dict.get(current_word, f"हिंदी अनुवाद ({current_word})")
    
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
            {hindi_word}
        </div>
        <div style="font-size: 1.3rem; font-style: italic; margin-bottom: 15px;">
            Example: "{current_word} is an important word to learn."
        </div>
        <div style="
            background: rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        ">
            <strong>💡 Tip:</strong> Practice saying "{current_word}" aloud 3 times
        </div>
    </div>
    """, unsafe_allow_html=True)

# Show all words
st.sidebar.markdown("---")
st.sidebar.subheader("All Words")
for i, word in enumerate(words):
    if i == idx:
        st.sidebar.markdown(f"**▶ {i+1}. {word}**")
    else:
        st.sidebar.write(f"{i+1}. {word}")

# Add a reset button
if st.sidebar.button("🔄 Reset to First Word"):
    st.session_state.current_index = 0
    st.session_state.show_hindi = False
    st.rerun()

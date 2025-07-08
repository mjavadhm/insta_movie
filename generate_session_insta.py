# generate_session.py

import instaloader
import os

# --- IMPORTANT ---
# Enter your Instagram username and password here
INSTAGRAM_USERNAME = "smjavad82j2@gmail.com"
INSTAGRAM_PASSWORD = "0150Javad-insta"
# -----------------

if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
    print("❌ Please enter your Instagram username and password in the script.")
else:
    try:
        L = instaloader.Instaloader()
        print(f"Logging in as {INSTAGRAM_USERNAME}...")
        
        # This is where you will interact with the script
        L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        
        print("✅ Login successful!")
        
        # Save the session to a file
        session_file = f"./{INSTAGRAM_USERNAME}"
        L.save_session_to_file(session_file)
        
        print(f"✅ Session saved successfully to file: {session_file}")
        print("Please upload this file to your server in the same directory as your bot.")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("If you see a 'Checkpoint required' error, open a browser and log in to Instagram to complete the security check, then run this script again.")
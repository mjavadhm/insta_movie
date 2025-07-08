# generate_session_insta.py

import instaloader
from getpass import getpass  # A secure way to ask for a password

# --- IMPORTANT ---
# Enter your Instagram username here
INSTAGRAM_USERNAME = "smjavad82j2@gmail.com"
# -----------------

if not INSTAGRAM_USERNAME:
    print("❌ Please enter your Instagram username in the script.")
else:
    L = instaloader.Instaloader()
    print("A new login is required.")
    
    try:
        # Ask for password and 2FA code in the terminal
        password = getpass(f"Enter password for {INSTAGRAM_USERNAME}: ")
        
        print("Logging in...")
        L.login(INSTAGRAM_USERNAME, password)
        
        print("✅ Login successful!")
        
        # Save the session to a file
        session_file = f"./{INSTAGRAM_USERNAME}"
        L.save_session_to_file(session_file)
        
        print(f"✅ Session saved successfully to file: {session_file}")
        print("You can now upload this file to your server.")

    except instaloader.exceptions.TwoFactorAuthRequiredException:
        print("Two-Factor Authentication is required.")
        two_factor_code = input("Enter the 2FA code from your authenticator app: ")
        try:
            L.two_factor_login(two_factor_code)
            print("✅ 2FA Login successful!")
            
            # Save the session after 2FA
            session_file = f"./{INSTAGRAM_USERNAME}"
            L.save_session_to_file(session_file)
            print(f"✅ Session saved successfully to file: {session_file}")

        except Exception as e_2fa:
            print(f"❌ An error occurred during 2FA login: {e_2fa}")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("Please make sure your password is correct and try again in a few minutes.")
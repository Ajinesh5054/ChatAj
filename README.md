# AjChatroom - From Scratch

Signup once, then Login.
Shared room URL -> Login when logged out -> returns to the room after login.
Already logged-in users open the room directly.
Host creates a room and gets a unique URL. Host can use it too.
Multiple accounts can use the same URL with real-time Socket.IO chat.

Local:
python -m pip install -r requirements.txt
python app.py
Open http://127.0.0.1:5000

Public internet access requires a hosting server. After one deployment, users only use the public URL.

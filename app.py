import os, secrets
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, flash, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash

BASE=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__)
app.config["SECRET_KEY"]=os.environ.get("SECRET_KEY","change-me")
app.config["SQLALCHEMY_DATABASE_URI"]="sqlite:///"+os.path.join(BASE,"chatroom.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
db=SQLAlchemy(app)
socketio=SocketIO(app,cors_allowed_origins="*",async_mode="threading")

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(80),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)

class Room(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(120),nullable=False)
    description=db.Column(db.String(300),default="")
    token=db.Column(db.String(64),unique=True,nullable=False)
    host_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    host=db.relationship("User")

@app.route("/")
def home():
    return redirect(url_for("chatrooms") if session.get("user_id") else url_for("login"))

@app.route("/signup",methods=["GET","POST"])
def signup():
    if session.get("user_id"): return redirect(url_for("chatrooms"))
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password",""); c=request.form.get("confirm","")
        if len(u)<3: flash("Username must contain at least 3 characters.","error")
        elif len(p)<6: flash("Password must contain at least 6 characters.","error")
        elif p!=c: flash("Passwords do not match.","error")
        elif User.query.filter_by(username=u).first():
            flash("Account already exists. Please login.","error"); return redirect(url_for("login"))
        else:
            db.session.add(User(username=u,password_hash=generate_password_hash(p))); db.session.commit()
            flash("Signup successful. Please login.","success"); return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if session.get("user_id"): return redirect(url_for("chatrooms"))
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password","")
        user=User.query.filter_by(username=u).first()
        if user and check_password_hash(user.password_hash,p):
            session.clear(); session["user_id"]=user.id; session["username"]=user.username
            nxt=request.form.get("next") or request.args.get("next")
            return redirect(nxt if nxt and nxt.startswith("/") else url_for("chatrooms"))
        flash("Invalid username or password.","error")
    return render_template("login.html",next_url=request.args.get("next",""))

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/chatrooms")
def chatrooms():
    if not session.get("user_id"): return redirect(url_for("login"))
    return render_template("chatrooms.html",rooms=Room.query.order_by(Room.created_at.desc()).all())

@app.route("/create-room",methods=["POST"])
def create_room():
    if not session.get("user_id"): return redirect(url_for("login"))
    name=request.form.get("name","").strip(); description=request.form.get("description","").strip()
    if not name: flash("Room name is required.","error"); return redirect(url_for("chatrooms"))
    token=secrets.token_urlsafe(18)
    room=Room(name=name,description=description,token=token,host_id=session["user_id"])
    db.session.add(room); db.session.commit()
    return render_template("room_created.html",room=room,share_url=url_for("room",token=token,_external=True))

@app.route("/room/<token>")
def room(token):
    # A shared room link always goes to LOGIN if the visitor is logged out.
    if not session.get("user_id"):
        return redirect(url_for("login",next=request.path))
    room_obj=Room.query.filter_by(token=token).first()
    if not room_obj:
        return render_template("error.html"),404
    return render_template("room.html",room=room_obj)

@socketio.on("join_chat")
def join_chat(data):
    if not session.get("user_id"): return
    token=str((data or {}).get("token",""))
    if Room.query.filter_by(token=token).first():
        join_room(token)
        emit("system_message",{"message":session["username"]+" joined the room."},to=token)

@socketio.on("send_message")
def send_message(data):
    if not session.get("user_id"): return
    token=str((data or {}).get("token",""))
    message=str((data or {}).get("message","")).strip()[:2000]
    if message and Room.query.filter_by(token=token).first():
        emit("receive_message",{"username":session["username"],"message":message,
            "time":datetime.now().strftime("%I:%M %p")},to=token)

@socketio.on("typing")
def typing(data):
    if session.get("user_id"):
        emit("typing",{"username":session["username"]},
             to=str((data or {}).get("token","")),include_self=False)

with app.app_context():
    db.create_all()

if __name__=="__main__":
    socketio.run(app,host="0.0.0.0",port=int(os.environ.get("PORT",5000)),
                 debug=False,allow_unsafe_werkzeug=True)

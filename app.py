from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_session import Session
from flask import Flask, redirect, url_for, session
from authlib.integrations.flask_client import OAuth
import os
from functools import wraps
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm import tqdm
import pandas as pd

from sklearn import preprocessing
from tensorflow import keras
from tensorflow.keras.models import load_model

modelr = pickle.load(open("timepass-RF.sav", 'rb'))
df = pd.read_csv("text-vector.csv")
text_vector = df['tokens'].tolist()

app = Flask(__name__)
app.debug = True

app.config['SECRET_KEY'] = 'secret'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
socketio = SocketIO(app, manage_session=False)

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id="138634578533-adelcfp3iku0c8jhekqulmrsfqcpnlrg.apps.googleusercontent.com",
    client_secret="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",
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    # This is only needed if using openId to fetch user info
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},

)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # checking if the there is admin login , if yes then admin gets all the desired session ids to perform admin actions.
        admin = dict(session).get('user_names', None)
        if admin:
            return f(*args, **kwargs)

        return render_template('401.html')
    return decorated_function


@app.route('/', methods=['GET', 'POST'])
def index():
    session.setdefault("filter_status", "deactivated")
    return render_template('index.html')


@app.route('/chatpage', methods=['GET', 'POST'])
@login_required
def chatpage():
    nameofuser = session['user_names']
    return render_template('chatpage.html',  nameofuser=nameofuser)


@app.route('/login')
def login():
    google = oauth.create_client('google')  # create the google oauth client
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/authorize')
def authorize():
    google = oauth.create_client('google')  # create the google oauth client
    # Access token from google (needed to get user info)
    token = google.authorize_access_token()
    # userinfo contains stuff u specificed in the scrope

    resp = google.get('userinfo')
    user_info = resp.json()
    user = oauth.google.userinfo()  # uses openid endpoint to fetch user info
    # Here you use the profile/user data that you got and query your database find/register the user
    # and set ur own data in the session not the profile from google
    session['user_email'] = user_info.get('email')
    session['logged_in'] = True
    session['user_names'] = user_info.get('name')
    print(user_info)
    session['profile'] = user_info
    # make the session permanant so it keeps existing after broweser gets closed
    session.permanent = False
    return redirect('/')


@app.route('/layout')
def layout():
    return render_template('layout.html')


@app.route('/logout')
def logout():
    for key in list(session.keys()):
        session.pop(key)
    return redirect('/')


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if(request.method == 'POST'):
        username = request.form['username']
        room = request.form['room']
        # Store the data in session
        session['username'] = username
        session['room'] = room
        return render_template('chat.html', session=session)
    else:
        if(session.get('username') is not None):
            return render_template('chat.html', session=session)
        else:
            return redirect(url_for('index'))


@socketio.on('join', namespace='/chat')
def join(message):
    room = session.get('room')
    join_room(room)
    sys = "System"
    newmsg = " has entered the room"
    emit('message', {'user': sys,
         'msg': session.get('username')+newmsg, 'err': 'join'}, room=room)
    # emit('status', {'msg':  session.get('username') +
    #      ' has entered the room.'}, room=room)


def toVect(a):
    vectorizer = TfidfVectorizer()
    untokenized_data = [''.join(tweet)
                        for tweet in tqdm(text_vector, "Vectorizing...")]
    # print(untokenized_data)
    vectorizer = vectorizer.fit(untokenized_data)
    rev = vectorizer.transform([a])
    # print(rev)
    return rev


def Predict_Next_Words(model, tokenizer, text):

    vector = tokenizer.transform([text]).todense()
    preds = model.predict(vector)
    # final = preprocessing.normalize(preds)
    if preds[0][0] >= 0.5:
        # print(final)
        return "OFF"
    else:
        return "NOT-OFF"


model = load_model('4898-53-47-tfidf-nn-20eps.h5')
tokenizer = pickle.load(open('4898-53-47-tfidf-nn-20eps.pkl', 'rb'))

list3 = ['fuck you', 'fuck',
         "madarchod", "madarc**d", "lavda", "la**ya", "a55", "@$$", "b!tch", "bho***ka", "ga*du", "pu$$y", ]


def censor(text):
    dummy = text
    for word in text.split():
        if word in list3:
            replc_word = ""
            i = 0
            for jk in word:
                if i % 2 == 0:
                    replc_word += jk
                else:
                    replc_word += "*"
                i += 1
            dummy = dummy.replace(word, replc_word)
    return dummy


@app.route("/filter", methods=["POST"])
def filter():
    selected_option = request.form["selected_option"]
    session["filter_status"] = selected_option

    if "filter_status" in session:
        if selected_option == "apply":
            session["filter_status"] = "activated"
        elif selected_option == "deactivate":
            session["filter_status"] = "deactivated"
        else:
            session["filter_status"] = "deactivated"
    return "Filter status updated: {}".format(session["filter_status"])


@socketio.on('text', namespace='/chat')
def text(message):
    room = session.get('room')
    result = Predict_Next_Words(model, tokenizer, message['msg'])
    result2 = modelr.predict(toVect(message['msg']))

    session['message-send'] = True
    print(session["filter_status"])

    if (session["filter_status"] == "activated"):
        # result3 = predictlist(message['msg'], list3)
        # if result == "OFF" or result2 == "OFF":

        #     newmsg = "MESSAGE DELETED DUE ITS OFFENSIVE NATURE"

        #     emit('message', {'user': session.get('username'),
        #                      'msg': newmsg, 'err': 'yes'}, room=room)
        # else:
        newmsg = censor(message['msg'])
        emit('message', {'user': session.get('username'),
                         'msg': newmsg, 'err': 'no'}, room=room)
    elif(session["filter_status"] == "deactivated"):
        print("inside this")
        if result == "OFF" or result2 == "OFF":

            newmsg = "MESSAGE DELETED DUE ITS OFFENSIVE NATURE"

            emit('message', {'user': session.get('username'),
                             'msg': newmsg, 'err': 'yes'}, room=room)
        else:
            newmsg = message['msg']
            emit('message', {'user': session.get('username'),
                             'msg': newmsg, 'err': 'no'}, room=room)


@socketio.on('left', namespace='/chat')
def left(message):
    room = session.get('room')
    username = session.get('username')
    leave_room(room)
    session.clear()
    sys = "System"
    newmsg = " has left the room"
    emit('message', {'user': sys,
         'msg':  username+newmsg, 'err': 'leave'}, room=room)
    # emit('status', {'msg': username + ' has left the room.'}, room=room)


if __name__ == '__main__':
    socketio.run(app)

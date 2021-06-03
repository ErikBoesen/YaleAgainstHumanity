import mebots
import os
import requests
from flask import Flask, request, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet
from threading import Thread
import json
import random


app = Flask(__name__)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)


def get_user_game(user_id):
    game_group_id = playing.get(user_id)
    if game_group_id is None:
        return None
    return games[game_group_id]


def process_message(message):
    print(message)
    if message["sender_type"] == "user":
        if message["text"].startswith(PREFIX):
            instructions = message["text"][len(PREFIX):].strip().split(None, 1)
            command = instructions.pop(0).lower()
            query = instructions[0] if len(instructions) > 0 else ""
            group_id = message.get("group_id")
            user_id = message.get("user_id")
            name = message.get("name")

            game = games.get(group_id)
            if command == "start":
                if game:
                    return "Game already started!"
                game = Game(group_id)
                games[group_id] = game
                # TODO: DRY
                playing[user_id] = group_id
                game.join(user_id, name)
                return (f"Cards Against Humanity game started. {name} added to game as first Czar. Play at https://botagainsthumanitygroupme.herokuapp.com/play.\n"
                        "Other players can say `CAH join` to join. `CAH end` will terminate the game.\n")
            elif command == "end":
                if game is None:
                    return "No game in progress."
                games.pop(group_id)
                for user_id in game.players:
                    playing.pop(user_id)
                return "Game ended. Say `CAH start` to start a new game."
            elif command == "join":
                if user_id in playing:
                    return "You're already in a game."
                if group_id not in games:
                    return "No game in progress. Say `CAH start` to start a game."
                # TODO: DRY
                playing[user_id] = group_id
                game.join(user_id, name)
                return f"{name} has joined the game! Please go to https://botagainsthumanitygroupme.herokuapp.com/play to play."
            elif command == "leave":
                if user_id in playing:
                    playing.pop(user_id)
                    # TODO: remove them from game also!!
                    # TODO: need to make sure they weren't czar or anything.
                    return f"Removed {name} from the game."
                else:
                    return f"{name} is not currently in a game."
            elif command == "info":
                return str(games) + " " + str(playing) + " " + str(self)


def api_get(endpoint, access_token):
    return requests.get(f"https://api.groupme.com/v3/users/{endpoint}?token={access_token}").json()["response"]


def get_me(access_token):
    return api_get("me", access_token)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/play", methods=["GET"])
def cah():
    return render_template("play.html")


@socketio.on("game_connect")
def game_connect(data):
    access_token = data["access_token"]
    # TODO: DRY!!
    user = get_me(access_token)
    user_id = user["user_id"]
    game = get_user_game(user_id)

    joined = game_ping(access_token, room=False)
    if joined:
        join_room(game.group_id)
        game_ping(access_token, single=False)


def game_ping(access_token, room=True, single=True):
    # TODO: These lines are repeated like three times what are you DOING
    # TODO: Clean this up in the morning when you're sane
    user = get_me(access_token)
    user_id = user["user_id"]
    game = get_user_game(user_id)
    if room:
        selection = [card for _, card in game.selection]
        emit("game_ping", {"black_card": game.current_black_card,
                           "selection_length": len(selection),
                           "selection": selection if game.players_needed() == 0 else None},
             room=game.group_id)
    if single:
        if game is None:
            emit("game_update_user", {"joined": False})
            return False
        player = game.players[user_id]
        is_czar = game.is_czar(user_id)
        emit("game_update_user", {"joined": True,
                                  "is_czar": is_czar,
                                  "hand": player.hand,
                                  "score": len(player.won)})
        return True


@socketio.on("game_selection")
def game_selection(data):
    user = get_me(access_token)
    user_id = user["user_id"]
    game = get_user_game(user_id)
    player = game.players[user_id]
    group_id = game.group_id
    if game.is_czar(user_id):
        card, player = game.czar_choose(data["card_index"])
        send("The Card Czar has selected \"{card}\" played by {name}, who now has a score of {score}.".format(card=card,
                                                                                                              name=player.name,
                                                                                                              score=len(player.won)), group_id)
        send("The next black card is \"{card}\" and {name} is now Czar.".format(card=game.current_black_card,
                                                                                name=player.name), group_id)
    else:
        permitted = game.player_choose(user_id, data["card_index"])
        remaining_players = game.players_needed()
        if permitted:
            send(f"{player.name} has played a card. {remaining_players} still need to play.", group_id)
    game_ping(access_token)

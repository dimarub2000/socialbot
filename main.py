import os
import random
import time
import threading
import telebot

from sqlalchemy import and_
from database import db
from database import User, Transaction
from pastes import pastes

bot = telebot.AsyncTeleBot(os.environ['BOT_TOKEN'])
bot.threaded = True

POSITIVE_OPTION = "agree"
NEGATIVE_OPTION = "nope"


def cur_time():
    return int(time.time())


def check_member(username, chat_id):
    return User.query.filter_by(username=username, chat_id=chat_id).first()


def make_credit_transaction(username, chat_id, credit):
    member = check_member(username, chat_id)
    if not member:
        return False

    transaction = Transaction(ts=cur_time(), username=username, chat_id=chat_id, credit=credit)
    member.credit += credit
    db.session.add(transaction)
    db.session.commit()
    bot.send_message(chat_id, "{:+} to {}".format(credit, username))
    return True


def is_credit_message(message):
    return message.reply_to_message and \
           message.sticker and \
           message.sticker.set_name == "PoohSocialCredit"


def is_add_credit_message(message):
    return is_credit_message(message) and message.sticker.emoji == "😄"


def is_sub_credit_message(message):
    return is_credit_message(message) and message.sticker.emoji == "😞"


def get_params_from_message(message):
    return message.from_user.username, message.chat.id


@bot.message_handler(func=is_add_credit_message, content_types=['sticker'])
def add_credit(message):
    username, chat_id = get_params_from_message(message)
    if not check_member(username, chat_id):
        bot.reply_to(message, "Not a club member, {}".format(username))
        return

    reply_username = message.reply_to_message.from_user.username
    if username == reply_username:
        bot.reply_to(message, "Shame on you, {}!".format(username))
        make_credit_transaction(reply_username, chat_id, -20)
        return
    make_credit_transaction(reply_username, chat_id, 20)


@bot.message_handler(func=is_sub_credit_message, content_types=['sticker'])
def sub_credit(message):
    username, chat_id = get_params_from_message(message)
    if not check_member(username, chat_id):
        bot.reply_to(message, "Not a club member, {}".format(username))
        return

    reply_username = message.reply_to_message.from_user.username
    if username == reply_username:
        bot.reply_to(message, "LOL Ok.")
    make_credit_transaction(reply_username, chat_id, -20)


@bot.message_handler(commands=['top'])
def top_handler(message):
    _, chat_id = get_params_from_message(message)
    users = sorted(User.query.filter_by(chat_id=chat_id).all(), key=lambda user: user.credit, reverse=True)
    if not users:
        bot.reply_to(message, "Club is empty =(. Join it with /register")
        return
    indent = len(max(users, key=lambda user: len(user.username)).username) + 1
    users_top = [("{:<%d} {}" % indent).format(user.username, user.credit) for user in users]
    bot.send_message(chat_id, "```\n" + "\n".join(users_top) + "\n```", parse_mode="MarkdownV2")


@bot.message_handler(commands=['register'])
def register_handler(message):
    username, chat_id = get_params_from_message(message)
    member = User.query.filter_by(username=username, chat_id=chat_id).first()
    if member:
        bot.reply_to(message, "Already in da club, {}".format(username))
        return

    bot.reply_to(message, "Welcome to the club, {}".format(username))
    user = User(username=username, chat_id=chat_id)
    db.session.add(user)
    db.session.commit()


def on_poll_finish(chat_id, msg_id, username, credit, transaction_ids):
    poll = bot.stop_poll(chat_id, msg_id).wait()
    poll_res = {option.text: option.voter_count for option in poll.options}

    poll_agreed = poll_res[POSITIVE_OPTION] > poll_res[NEGATIVE_OPTION] and poll.total_voter_count >= 2
    if poll_agreed:
        make_credit_transaction(username, chat_id, credit)

    transactions = db.session.query(Transaction).filter(Transaction.id.in_(transaction_ids)).all()
    for transaction in transactions:
        transaction.state = 2 if poll_agreed else 0
    db.session.commit()


@bot.message_handler(commands=['pochemy'])
def pochemy_handler(message):
    username, chat_id = get_params_from_message(message)
    if not check_member(username, chat_id):
        bot.reply_to(message, "Not a club member, {}".format(username))
        return

    transactions = db.session.query(Transaction) \
        .filter_by(username=username, chat_id=chat_id) \
        .filter(and_(Transaction.credit < 0, Transaction.ts > cur_time() - 60 * 2, Transaction.state == 0))

    credit = 0
    transaction_ids = []
    for transaction in transactions:
        transaction.state = 1
        credit -= transaction.credit
        transaction_ids.append(transaction.id)
    db.session.commit()

    if not transaction_ids:
        bot.reply_to(message, "Chill out, {}".format(username))
        return

    poll = bot.send_poll(
        chat_id=chat_id,
        question="{} requested amnesty for {}".format(username, credit),
        options=[POSITIVE_OPTION, NEGATIVE_OPTION]
    ).wait()

    threading.Timer(30, on_poll_finish, kwargs={
        "chat_id": chat_id,
        "msg_id": poll.message_id,
        "username": username,
        "credit": credit,
        "transaction_ids": transaction_ids,
    }).start()


@bot.message_handler(commands=['pasta'])
def pasta_handler(message):
    _, chat_id = get_params_from_message(message)
    paste = pastes[random.randint(0, len(pastes) - 1)]
    bot.send_message(chat_id, paste)


if __name__ == "__main__":
    db.create_all()
    bot.polling(none_stop=True, interval=0)

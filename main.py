import os
import time
import telebot
import threading
from sqlalchemy import func, and_
from database import db
from database import User, Transaction

bot = telebot.AsyncTeleBot(os.environ['BOT_TOKEN'])
bot.threaded = True

POSITIVE_OPTION = "agree"
NEGATIVE_OPTION = "nope"


def cur_time():
    return int(time.time())


def make_credit_transaction(username, chat_id, credit):
    member = User.query.filter_by(username=username, chat_id=chat_id).first()
    if not member:
        return False
    transaction = Transaction(ts=cur_time(), username=username, chat_id=chat_id, credit=credit)
    member.credit += credit
    db.session.add(transaction)
    db.session.commit()
    bot.send_message(chat_id, "{} to {}".format(credit, username))
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
    reply_username = message.reply_to_message.from_user.username
    if username == reply_username:
        bot.reply_to(message, "Shame on you, {}!".format(username))
        make_credit_transaction(reply_username, chat_id, -20)
        return
    make_credit_transaction(reply_username, chat_id, 20)


@bot.message_handler(func=is_sub_credit_message, content_types=['sticker'])
def sub_credit(message):
    username, chat_id = get_params_from_message(message)
    reply_username = message.reply_to_message.from_user.username
    if username == reply_username:
        bot.reply_to(message, "LOL OK")
    make_credit_transaction(reply_username, chat_id, -20)


@bot.message_handler(commands=['top'])
def top(message):
    _, chat_id = get_params_from_message(message)
    users = sorted(User.query.filter_by(chat_id=chat_id).all(), key=lambda user: user.credit, reverse=True)
    users_top = ["{}:{}".format(user.username, user.credit) for user in users]
    bot.send_message(chat_id, "\n".join(users_top))


@bot.message_handler(commands=['register'])
def register(message):
    username, chat_id = get_params_from_message(message)
    member = User.query.filter_by(username=username, chat_id=chat_id).first()
    if member:
        bot.reply_to(message, "Already in da club, {}".format(username))
        return

    bot.reply_to(message, "Welcome to the club, {}".format(username))
    user = User(username=username, chat_id=chat_id)
    db.session.add(user)
    db.session.commit()


def on_poll_finish(chat_id, msg_id, username, credit):
    task = bot.stop_poll(chat_id, msg_id)
    poll = task.wait()
    poll_results = {option.text: option.voter_count for option in poll.options}
    if poll_results[POSITIVE_OPTION] > poll_results[NEGATIVE_OPTION] and poll.total_voter_count >= 2:
        make_credit_transaction(username, chat_id, credit)
        db.session.query(Transaction) \
            .filter_by(username=username, chat_id=chat_id) \
            .filter(and_(Transaction.credit < 0, Transaction.ts > cur_time() - 60 * 2)) \
            .delete(synchronize_session=False)
        db.session.commit()


@bot.message_handler(commands=['pochemy'])
def pochemy(message):
    username, chat_id = get_params_from_message(message)
    transactions = db.session.query(Transaction) \
        .filter_by(username=username, chat_id=chat_id) \
        .filter(and_(Transaction.credit < 0, Transaction.ts > cur_time() - 60 * 2))
    credit = sum(map(lambda t: -t.credit, transactions))
    if credit == 0:
        bot.reply_to(message, "Chill out, {}".format(username))
        return
    task = bot.send_poll(
        chat_id=message.chat.id,
        question="{} requested amnesty for {} credit".format(username, credit),
        options=[POSITIVE_OPTION, NEGATIVE_OPTION]
    )
    poll = task.wait()
    threading.Timer(30, on_poll_finish, kwargs={
        "chat_id": chat_id,
        "msg_id": poll.message_id,
        "username": username,
        "credit": credit,
    }).start()


if __name__ == "__main__":
    db.create_all()
    bot.polling(none_stop=True, interval=0)

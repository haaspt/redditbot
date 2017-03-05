from __future__ import print_function
import argparse
import time
import praw
import re
import sqlite3
import logging
import os.path
from config import Credentials, Parameters

def db_init(cursor):

    # Optional DB refresh
    if args.user_refresh:
        cursor.execute("DROP TABLE users;")
    if args.refresh:
        cursor.execute("DROP TABLE post_archive;")
        cursor.execute("DROP TABLE valid_posts;")
            
    # Creates default tables if they don't already exist
    cursor.execute("CREATE TABLE IF NOT EXISTS post_archive (id PRIMARY KEY, timestamp INT, subreddit_id TEXT);")
    cursor.execute("CREATE TABLE IF NOT EXISTS valid_posts (id PRIMARY KEY, username TEXT, user_id TEXT, timestamp INT, post_title TEXT, post_text TEXT, replied BOOL);")
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id PRIMARY KEY, username TEXT, last_message_date INT, blacklisted BOOL);")

def submission_search(subreddit, regex_pattern, cursor):

    # Sets the default limit to 1,000
    # Iteration will terminate early if previous max timetamp encountered
    submissions = subreddit.new(limit=1000)
    
    # Get most recent post timestamp, based on previous time DB was updated
    logger.debug("Searching for most recent prior search of %s", subreddit.name)
    cursor.execute('SELECT MAX(timestamp) FROM post_archive WHERE subreddit_id = ?;',
                   (subreddit.id,))
    fetch = cursor.fetchone()
    max_timestamp = fetch[0]
    
    if max_timestamp is None:
        logger.info("No prior timestamp found. Most recent 1000 submissions will be checked")
        max_timestamp = 0

    # Iterates through submissions until a post older than the last max timestamp is encountered
    # All posts saved to the archive. Valid posts saved to valid_posts
    submission_counter = 0
    new_submission_counter = 0
    valid_post_counter = 0
    
    for submission in submissions:
        submission_counter += 1
        if submission.created > max_timestamp:
            new_submission_counter += 1
            cursor.execute('INSERT INTO post_archive (id, timestamp, subreddit_id) VALUES (?, ?, ?);',
                           (submission.id, submission.created, subreddit.id))
            if regex_pattern.search(submission.title) is not None and submission.author is not None:
                valid_post_counter += 1
                logger.debug("Submission meets search criteria, adding to database")
                cursor.execute('INSERT INTO valid_posts (id, username, user_id, timestamp, post_title, post_text, replied) VALUES (?, ?, ?, ?, ?, ?, ?);',
                               (submission.id, submission.author.name, submission.author.id, submission.created, submission.title, submission.selftext, False))
            time.sleep(0.1)
        else:
            logger.debug("No new submissions to search")
            break

    logger.debug("Search finished after reviewing %d records.", submission_counter)
    logger.info("%d new submissions found, out of which %d met criteria.", new_submission_counter, valid_post_counter)
        

def blacklist_user(user, cursor):

    logger.debug("Blacklisting %s", user.name)
    # Inserts blacklisted username into DB, if it isn't already there
    cursor.execute('INSERT OR IGNORE INTO users (username, id, blacklisted) VALUES (?, ?, 1);',(user.name, user.id))


def reply_to_posts(reddit_api, cursor):

    # Selects Redditor info from valid_posts, checking that the post or user weren't already replied to
    cursor.execute("SELECT id, username, user_id FROM valid_posts WHERE replied = 0 AND username NOT IN (SELECT username FROM users);")
    posts_to_reply_to = cursor.fetchall()
    logger.info("Replying to %d posts", len(posts_to_reply_to))
    
    for post_record in posts_to_reply_to:
        post_id = post_record[0]
        username = post_record[1]
        logger.debug("Fetching redditor object for user %s", username)
        user = reddit_api.redditor(username)
        logger.info("Replying to %s", user.name)
        if not args.dryrun:
            # Checks if a user was already messaged
            user_already_messaged = user_already_messaged(user.id, cursor)
            if not user_already_messaged:
                message_user(user)
            else:
                logger.info("User %d already messaged, skipping", user.name)
                continue
        cursor.execute("UPDATE valid_posts SET replied = 1 WHERE id = ?;", (post_id,))
        cursor.execute("INSERT OR REPLACE INTO users (id, username, last_message_date) VALUES (?, ?, ?);", (user.id, user.name, int(time.time())))

def message_user(user):

    message = Parameters.message
    subject = Parameters.subject

    user.message(subject=subject, message=message)
    logger.debug("Redditor %s sucessfully messaged", user.name)


def user_already_messaged(user_id, cursor):

    cursor.execute('SELECT last_message_date FROM users WHERE id = ?;' (user_id))
    result = cursor.fetchone()
    if result is None:
        already_messaged = False
    else:
        already_messaged = True

    return already_messaged

def main():

    # DB initialization
    logger.info("Initializing database")
    connect = sqlite3.connect(DB_FILE)
    cursor = connect.cursor()
    db_init(cursor)
    logger.debug("Database initialized")

    # Reddit initialization
    logger.info("Initializing Reddit connection")
    reddit = praw.Reddit(client_id = Credentials.client_id,
                         client_secret = Credentials.client_secret,
                         user_agent = Credentials.user_agent,
                         username = Credentials.username,
                         password = Credentials.password)

    # Test message
    if args.message_test:
        logger.info("Sending a test message to yourself")
        me = reddit.redditor(Credentials.username)
        message_user(me)
        logger.info("Test complete, exiting")
        quit()

    # Regex search string compiled
    logger.debug("Loading regex query")
    regex = re.compile(Parameters.regex_search)

    # User defined blacklist updated
    logger.debug("Updating user blacklist")
    blacklist = Parameters.blacklisted_users
    logger.debug("Blacklisting %d users", len(blacklist))
    for user in blacklist:
        redditor = reddit.redditor(user)
        blacklist_user(redditor, cursor)
        connect.commit()

    # Iterates through defined subreddits, searching for posts that match regex criteria
    logger.info("Beginning subreddit search")
    subreddits = Parameters.subreddits_to_search
    logger.debug("Searching %d subreddits", len(subreddits))
    for sub_name in subreddits:
        logger.debug("Beginning search of %s", sub_name)
        sub = reddit.subreddit(sub_name)
        submission_search(sub, regex, cursor)
        connect.commit()

    # Send messages for valid posts
    if not args.update:
        reply_to_posts(reddit, cursor)
        connect.commit()
    
if __name__ == '__main__':

    DIR = os.path.dirname(os.path.realpath(__file__))
    LOG_FILE = DIR + '/applog.log'
    DB_FILE = DIR + '/app.db'
    
    logging.basicConfig(filename=LOG_FILE,
                        format='%(asctime)s-%(name)s :: %(levelname)s :: %(message)s',
                        level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.debug("Entering main loop")

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dryrun", help="updates the database and simulates messaging users without actually sending.",
                        action="store_true")
    parser.add_argument("-u", "--update", help="checks for new submissions and updates the post databases without sending messages.",
                        action="store_true")
    parser.add_argument("-r", "--refresh", help="performs a full refresh of the post DBs, dropping old values. User DB is unaffected.",
                        action="store_true")
    parser.add_argument("--user_refresh", help="performs a full refresh of the user DB. WARNING: this will erase your record of users you've already messaged",
                        action="store_true")
    parser.add_argument("--message_test", help="sends a test message to the authenticated user (aka messages yourself",
                        action="store_true")
    args = parser.parse_args()
    
    main()

# Redditbot
## Overview
Redditbot is a simple script, written in Python, designed to search a subreddit for new posts, store them in an SQLite3 database, and optionally send a message to a posts' author.

## Installation and Use
### Install
To install simply clone the repository into a desired directory:
`https://github.com/haaspt/redditbot.git`
Install required dependencies:
`pip install -r requirements.txt`

### Setup
Redditbot requires users to create a [Reddit](https://www.reddit.com) account and register an app through the [developers' tool](https://ssl.reddit.com/prefs/apps).

Once this is done, copy and rename config.py.sample to config.py. Edit the config.py file with your preferred text editor with the following values:

* Credentials: Your OAuth credentials from Reddit (for more details see the [praw docs](http://praw.readthedocs.io/en/latest/getting_started/authentication.html))
* Regex Search: The regex pattern you want to match to submission titles.
* Subreddits to Search: A list of subreddit names you wish to search for new matches in.
* Message: The text of the message you'd like to send to redditors who author matching posts.
* Subject: The subject line of the above message.

### Dependencies
* [praw](https://praw.readthedocs.io/en/latest/)
#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2011 Puneeth Chaganti <punchagan@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# A portion of this code is from the code of JabberBot copyrighted by
# Thomas Perl the copyright of which is included below.
# JabberBot: A simple jabber/xmpp bot framework
#
# Copyright (c) 2007-2011 Thomas Perl <thp.io/about>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commentary:
#
# This bot is written to behave like a chatroom, where all the
# messages are sent to all the users subscribed to this bot.
#
# You are required to have a file settings.py with the variables,
# JID, PASSWORD, CHANNEL, RES
#
# Depends: python-jabberbot, xmpppy
#

from jabberbot import JabberBot, botcmd

import xmpp
import collections
import threading
import time
import logging
import traceback
import codecs
from datetime import timedelta, datetime
from textwrap import dedent

import re, os, sys
import urllib2, urllib
import simplejson
from subprocess import Popen, PIPE, call

import meme
import poll

try:
    from BeautifulSoup import BeautifulSoup
    import gdata.youtube.service
except:
    print "Some features will not work, unless you have BeautifulSoup and gdata"
    

class ChatRoomJabberBot(JabberBot):
    """A bot based on JabberBot and broadcast example given in there."""

    def __init__( self, jid, password, res = None):
        super( ChatRoomJabberBot, self).__init__( jid, password, res)
        # create console handler
        chandler = logging.StreamHandler()
        # create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        # add formatter to handler
        chandler.setFormatter(formatter)
        # add handler to logger
        self.log.addHandler(chandler)
        # set level to INFO
        self.log.setLevel(logging.INFO)

        self.ops = {
            '++' : (re.compile(r'([a-zA-Z0-9]+)\+\+'), lambda x: x + 1, 'w00t!') ,
            '--' : (re.compile(r'([a-zA-Z0-9]+)--'), lambda x: x - 1, 'ouch!'), 
            }

        try:
            from state import MINILOGMAX
            self.MINILOGMAX = int(MINILOGMAX)
        except Exception, e:
            self.log.exception(e)
            self.MINILOGMAX=5

        self.sub_expression = re.compile(r"s/([a-zA-Z0-9-_\s]+)/([a-zA-Z0-9-_\s]+)/")
        # for s/// expresions
        self.mini_log = {}
        
        self.users = self.get_users()

        self.invited = self.get_invited()

        self.ideas = self.get_ideas()

        self.words = self.get_words()

        self.started = time.time()

        self.message_queue = []
        self.thread_killed = False

    def connect(self):
        if not self.conn:
            conn = xmpp.Client(self.jid.getDomain(), debug = [])

            if self.jid.getDomain() == 'gmail.com':
                conres = conn.connect(server=('talk.google.com', 5222))
            else:
                conres = conn.connect()

            if not conres:
                self.log.error('unable to connect to server %s.' % self.jid.getDomain())
                return None
            if conres<>'tls':
                self.log.warning('unable to establish secure connection - TLS failed!')
            else:
                self.log.info('Connected to server')

            authres = conn.auth(self.jid.getNode(), self._JabberBot__password, self.res)
            if not authres:
                self.log.error('unable to authorize with server.')
                self.attempt_reconnect()

            if authres<>'sasl':
                self.log.warning("unable to perform SASL auth os %s. Old authentication method used!" % self.jid.getDomain())

            conn.sendInitPresence()
            self.conn = conn
            self.roster = self.conn.Roster.getRoster()
            self.log.info('*** roster ***')
            for contact in self.roster.getItems():
                self.log.info('  %s' % contact)
            self.log.info('*** roster ***')
            self.conn.RegisterHandler('message', self.callback_message)
            self.conn.RegisterDisconnectHandler(self.attempt_reconnect)
            self.conn.UnregisterDisconnectHandler(conn.DisconnectHandler)
            self._JabberBot__set_status(self.get_topic())

        return self.conn

    def save_state(self):
        f = open('state.py', 'w')
        f.write('# -*- coding: utf-8 -*-\n\n')
        f.write('MINILOGMAX = %d\n\n' % self.MINILOGMAX)
        self.save_users(f)
        self.save_invited(f)
        self.save_topic(f)
        self.save_ideas(f)
        self.save_words(f)
        f.close()

    def get_users(self):
        try:
            from state import USERS
            users = USERS
            for user in users:
                users[user] = users[user].decode('utf-8')
            self.log.info("Obtained user data")
        except:
            users = {}
            self.log.info("No existing user data")
        return users

    def save_users(self, file):
        try:
            file.write('USERS = {\n')
            for u in self.users:
                file.write("'%s': '%s',\n"
                           %(u.encode('utf-8'),
                             self.users[u].encode('utf-8')))
            file.write('}\n\n')
            self.log.info("Saved user data")
        except:
            self.log.info("Couldn't save user data")


    def get_words(self):
        try:
            from state import WORDS
            words = WORDS
            for word in words:
                words[word] = int(words[word])
            self.log.info("Obtained word")
        except:
            words = {}
            self.log.info("No existing words")
        return words

    def save_words(self, file):
        try:
            file.write('WORDS = {\n')
            for word in self.words:
                file.write("'%s': '%d',\n"
                           %(word.encode('utf-8'),
                             int(self.words[word])))
            file.write('}\n\n')
            self.log.info("Saved words")
        except:
            self.log.info("Couldn't save words")



    def get_invited(self):
        try:
            from state import INVITED
            invited = INVITED
            for user in invited:
                invited[user] = invited[user].decode('utf-8')
            self.log.info("Obtained invited user data")
        except:
            invited = {}
            self.log.info("No existing invited users")
        return invited

    def save_invited(self, file):
        try:
            file.write('INVITED = {\n')
            for u in self.invited:
                file.write("'%s': '%s',\n" %(u, self.invited[u].encode('utf-8')))
            file.write('}\n\n')
            self.log.info("Saved invited user data")
        except:
            self.log.info("Couldn't save invited user data")

    def get_topic(self):
        try:
            from state import TOPIC
            TOPIC = TOPIC.decode('utf-8')
            return TOPIC
        except:
            return ''

    def save_topic(self, file):
        try:
            file.write('TOPIC = """%s"""\n\n' %(self._JabberBot__status.encode('utf-8')))
        except:
            return ''

    def get_ideas(self):
        try:
            from state import IDEAS
            ideas = [idea.decode('utf-8') for idea in IDEAS]
        except:
            ideas = []
        return ideas

    def save_ideas(self, file):
        try:
            file.write('IDEAS = [\n')
            for u in self.ideas:
                file.write('"""%s""",\n' % (u.encode('utf-8')))
            file.write(']\n\n')
        except:
            self.log.info("Couldn't save ideas")

    def shutdown(self):
        self.save_state()

    def attempt_reconnect(self):
        self.log.info('Restarting...')
        self.log.info('Pulling changes from GitHub...')
        call(["git", "pull"])
        os.execl('/usr/bin/nohup', sys.executable, sys.executable,
                 os.path.abspath(__file__))

    def get_sender_username(self, mess):
        """Extract the sender's user name (along with domain) from a message."""
        jid = mess.getFrom()
        typ = mess.getType()
        username = jid.getNode()
        domain = jid.getDomain()
        if typ == "chat":
            return "%s@%s" %(username, domain)
        else:
            return ""

    def unknown_command(self, mess, cmd, args):
        user = self.get_sender_username(mess)
        if user in self.users:
            self.message_queue.append('[%s]: %s %s' % (self.users[user], cmd, args))
            self.log.info("%s sent: %s %s" %(user, cmd, args))
        return ''


    def callback_message( self, conn, mess):
        """Messages sent to the bot will arrive here. Command handling + routing is done in this function."""

        jid      = mess.getFrom()
        props    = mess.getProperties()
        text     = mess.getBody()
        username = self.get_sender_username(mess)

        if username not in self.users.keys() + self.invited.keys():
            self.log.info("Ignored message from %s." % username)
            return

        self.log.debug("*** props = %s" % props)
        self.log.debug("*** jid = %s" % jid)
        self.log.debug("*** username = %s" % username)
        self.log.debug("*** type = %s" % type)
        self.log.debug("*** text = %s" % text)

        # Ignore messages from before we joined
        if xmpp.NS_DELAY in props: return

        # If a message format is not supported (eg. encrypted), txt will be None
        if not text: return

        # Remember the last-talked-in thread for replies
        self._JabberBot__threads[jid] = mess.getThread()

        if ' ' in text:
            command, args = text.split(' ', 1)
        else:
            command, args = text, ''
        cmd = command
        self.log.debug("*** cmd = %s" % cmd)

        # parse operators, commands, etc and if not, dump the message to the chat
        if self.apply_operator(mess, args):
            return

        if self.replace_text(username, mess):
            return

        if self.commands.has_key(cmd) and cmd != 'help':
            try:
                reply = self.commands[cmd](mess, args)
            except Exception, e:
                reply = traceback.format_exc(e)
                self.log.exception('An error happened while processing a message ("%s") from %s: %s"' % (text, jid, reply))
        else:
            # In private chat, it's okay for the bot to always respond.
            # In group chat, the bot should silently ignore commands it
            # doesn't understand or aren't handled by unknown_command().
            default_reply = 'Unknown command: "%s". Type "help" for available commands.<b>blubb!</b>' % cmd
            if type == "groupchat": default_reply = None
            reply = self.unknown_command( mess, cmd, args)
            if reply is None:
                reply = default_reply

        if reply:
            self.send_simple_reply(mess,reply)

        self.log_to_mini_log(username, text)


    def log_to_mini_log(self, username, text):
        # mini_log for s///
        mini_log = None
        try:
            mini_log = self.mini_log[username]
        except KeyError:
            try:
                mini_log = collections.deque([],self.MINILOGMAX)
            except TypeError:
                mini_log = collections.deque()
            self.mini_log[username] = mini_log
        mini_log.append(text)
        self.log.info("mini_log: %s" % (mini_log))

    def replace_text(self, username, mess):
        text = mess.getBody()
        if not self.sub_expression.match(text):
            return False

        match = self.sub_expression.match(text).group(1)
        replace = self.sub_expression.match(text).group(2)
        try:
        	mini_log = self.mini_log[username]
        	for phrase in mini_log:
        	    if match in phrase:
        	        new_phrase = phrase.replace(match,replace)
        	        self.message_queue.append('_%s meant %s_' %(self.users[username], new_phrase))
                        self.mini_log[username].append(new_phrase)
                        return
        except KeyError:
            # no mini_log, we create it on the 1st phrase
            pass
        # nothing found, inform
        reply = "No message found that matches that pattern."
        self.send_simple_reply(mess,reply)
        return True

    @botcmd(name=',restart')
    def restart(self, mess, args):
        """Restart the bot. Use resource name as PASSWORD.

        To avoid accidental restarts, resource name is used as argument.
        """
        user = self.get_sender_username(mess)

        if user in self.users and args.strip() == self.res:
            self.message_queue.append('_%s restarted me! brb!_'
                                       %(self.users[user]))
            self.log.info( '%s is restarting me.' % user)
            self.shutdown()
            self.idle_proc()
            self.conn.sendPresence(typ='unavailable')
            self.attempt_reconnect()

    @botcmd(name=',subscribe')
    def subscribe( self, mess, args):
        """Subscribe to the broadcast list"""
        user = self.get_sender_username(mess)
        if user in self.users:
            return 'You are already subscribed.'
        else:
            self.users[user] = user
            self.invited.pop(user)
            self.message_queue.append('_%s has joined the channel_' % user)
            self.log.info('%s subscribed to the broadcast.' % user)
            self.save_state()
            return 'You are now subscribed.'

    @botcmd(name=',unsubscribe')
    def unsubscribe( self, mess, args):
        """Unsubscribe from the broadcast list"""
        user = self.get_sender_username(mess)
        if not user in self.users:
            return 'You are not subscribed!'
        else:
            user = self.users.pop(user)
            self.message_queue.append('_%s has left the channel_' % user)
            self.log.info( '%s unsubscribed from the broadcast.' % user)
            self.save_state()
            return 'You are now unsubscribed.'


    @botcmd(name=',alias')
    def alias( self, mess, args):
        """Change your nick"""
        user = self.get_sender_username(mess)
        args = args.strip().replace(' ', '_')
        if user in self.users:
            if 0 < len(args) < 24 and args not in self.users.values():
                self.message_queue.append('_%s is now known as %s_' %(self.users[user], args))
                self.users[user] = args
                self.log.info( '%s changed alias.' % user)
                self.log.info('%s' %self.users)
                self.save_state()
                return 'You are now known as %s' % args
            else:
                return 'Nick already taken, or too short/long. 1-24 chars allowed.'
                   
    def apply_operator(self, mess, args):
        """w00ts"""
        msg = '_%s: %s [%s now at %d]_'
        user = self.get_sender_username(mess)
        text = mess.getBody()
        for op in self.ops:
            (regex, func, string) = self.ops[op]
            match = regex.match(text)
            if match is not None:                
                if match.group(1) in self.words:
                    counter = self.words[match.group(1)]
                    counter = func(counter)
                    self.words[match.group(1)] = counter
                    self.message_queue.append(msg %(self.users[user], match.group(0), string, counter))
                else:
                    counter = 0
                    counter = func(counter)
                    self.words[match.group(1)] = counter
                    self.message_queue.append(msg %(self.users[user], match.group(0), string, counter))
                return True
        return False

                   
    @botcmd(name=',topic')
    def topic( self, mess, args):
        """Change the topic/status"""
        user = self.get_sender_username(mess)
        if user in self.users:
            self._JabberBot__set_status(args)
            self.message_queue.append('_%s changed topic to %s_' %(self.users[user], args))
            self.log.info( '%s changed topic.' % user)
            self.save_state()

    @botcmd(name=',meme')
    def meme( self, mess, args):
        """Create a meme, for the lulz"""
        user = self.get_sender_username(mess)
        if user in self.users:
            try:
                meme_id = args.split(' ')[0]
                if meme_id == 'help':
                    memes = meme.list_memes()
                    help_msg = "usage: ,meme meme 'top text' 'button text' where meme is %s" % memes 
                    return help_msg

                parsed = args.split('\'')
                (top, button) = (parsed[1], parsed[3])
                meme_url = meme.create_meme(meme_id, top, button)
                self.message_queue.append('_%s created a meme %s _' %(self.users[user], meme_url))
                self.log.info( '%s created a meme, for the lulz' % user)

            except Exception:
                self.log.info( '%s tried to create a meme, but failed' % user)


    @botcmd(name=',list')
    def list( self, mess, args):
        """List all the members of the list"""
        user = self.get_sender_username(mess)
        args = args.replace(' ', '_')
        if user in self.users:
            user_list = 'All these users are subscribed - \n'
            user_list += '\n'.join(['%s :: %s' %(u, self.users[u]) for u in sorted(self.users)])
            if self.invited.keys():
                user_list += '\n The following users are invited - \n'
                user_list += '\n'.join(self.invited.keys())
            self.log.info( '%s checks list of users.' % user)
            return user_list

    @botcmd(name=',me')
    def myself(self, mess, args):
        """Send message in third person"""
        user = self.get_sender_username(mess)
        if user in self.users:
            self.message_queue.append('_%s %s_' % (self.users[user], args))
            self.log.info( '%s says %s in third person.' % (user, args))


    @botcmd(name=',invite')
    def invite(self, mess, args):
        """Invite a person to join the room. Works only if the person has added the bot as a friend, as of now."""
        user = self.get_sender_username(mess)
        if user in self.users:
            self.send(args, '%s invited you to join %s. Say ",help" to see how to join.' % (user, CHANNEL))
            self.invited['%s@%s' %(xmpp.JID(args).getNode(), xmpp.JID(args).getDomain())] = ''
            self.log.info( '%s invited %s.' % (user, args))
            self.save_state()
            self.message_queue.append('_%s invited %s_' % (self.users[user], args))

    @botcmd(name=',ideas')
    def ideas(self, mess, args):
        """Maintain a list of ideas/items. Use ,ideas help."""
        user = self.get_sender_username(mess)
        if user in self.users:
            if args.startswith('show'):
                txt = '\n_%s is ideating_\n' % (self.users[user])
                for i, idea in enumerate(self.ideas):
                    txt += '_%s - %s_\n' % (i, idea)
                self.message_queue.append(txt)
            elif args.startswith('add'):
                text = ' '.join(args.split()[1:]).strip()
                if text == '':
                    return "Sorry. Cannot add empty idea."
                self.ideas.append(text)
                self.save_state()
                self.message_queue.append('_%s added "%s" as an idea_' % (self.users[user], text))
            elif args.startswith('del'):
                try:
                    num = int(args.split()[1])
                    if num in range(len(self.ideas)):
                        self.message_queue.append('_%s deleted "%s" from ideas_' % (self.users[user], self.ideas[num]))
                        del self.ideas[num]
                        self.save_state()
                except:
                    return "Invalid option to delete."
            elif args.startswith('edit'):
                try:
                    num = int(args.split()[1])
                    if num in range(len(self.ideas)):
                        txt = ' '.join(args.split()[2:]).strip()
                        if txt == '':
                            return "Sorry. Cannot add empty idea."
                        self.message_queue.append('_%s changed idea %s to %s_' % (self.users[user], num, txt))
                        self.ideas[num] = txt
                        self.save_state()
                except:
                    return "Invalid option to edit."
            elif not args:
                return '\n'.join(['_%s - %s_' %(i,t) for i,t in enumerate(self.ideas)])
            else:
                return """add - Adds a new idea
                del n - Deletes n^{th} idea
                edit n txt - Replace n^{th} idea with 'txt'
                show - Show ideas in chatroom
                no arguments - Show ideas to you"""

    @botcmd(name=',whois')
    def whois( self, mess, args):
        """Check who has a particular nick"""
        user = self.get_sender_username(mess)
        args = args.strip().replace(' ', '_')
        if user in self.users:
            self.log.info('%s queried whois %s.' % (user, args))
            if args in self.users.values():
                return filter(lambda u: self.users[u] == args, self.users)[0]
            else:
                return 'Nobody!'

    @botcmd(name=',uptime')
    def uptime(self, mess, args):
        """Check the uptime of the bot."""
        user = self.get_sender_username(mess)
        if user in self.users:
            t = datetime.fromtimestamp(time.time()) - \
                   datetime.fromtimestamp(self.started)
            hours = t.seconds/3600
            mins = (t.seconds/60)%60
            secs = t.seconds%60
            self.log.info('%s queried uptime.' % (user))
            self.message_queue.append("Harbouring conversations, and what's more, memories, relentlessly since %s day(s) %s hour(s) %s min(s) and %s sec(s) for %s & friends" % (t.days, hours, mins, secs, self.users[user]))

    @botcmd(name=',yt')
    def youtube_fetch(self, mess, args):
        """Fetch the top-most result from YouTube"""
        user = self.get_sender_username(mess)
        if user in self.users:
            self.log.info('%s queried %s from Youtube.' % (user, args))
            yt_service = gdata.youtube.service.YouTubeService()
            query = gdata.youtube.service.YouTubeVideoQuery()
            query.racy = 'include'
            query.orderby = 'relevance'
            query.max_results = 1
            query.vq = args

            feed = yt_service.YouTubeQuery(query)
            self.message_queue.append('%s searched for %s ...' %(self.users[user], args))

            for entry in feed.entry:
                self.message_queue.append('... and here you go -- %s' % entry.GetHtmlLink().href)

    @botcmd(name=',g')
    def google_fetch(self, mess, args):
        """Fetch the top-most result from Google"""
        user = self.get_sender_username(mess)
        if user in self.users:
            self.log.info('%s queried %s from Google.' % (user, args))
            query = urllib.urlencode({'q' : args})
            url = 'http://ajax.googleapis.com/ajax/' + \
                  'services/search/web?v=1.0&%s' % (query)
            results = urllib.urlopen(url)
            json = simplejson.loads(results.read())
            self.message_queue.append('%s googled for %s ... and here you go'
                                      %(self.users[user], args))
            try:
                top = json['responseData']['results'][0]
                self.message_queue.append('%s -- %s' %(top['title'], top['url']))
            except:
                self.message_queue.append('%s' % "Oops! Nothing found!")

    @botcmd(name=',sc')
    def soundcloud_fetch(self, mess, args):
        """Fetch the top-most result from Google for site: soundcloud.com"""
        user = self.get_sender_username(mess)
        if user in self.users:
            self.log.info('%s queried %s from Google.' % (user, args))
            query = urllib.urlencode({'q' : "site:soundcloud.com " + args})
            url = 'http://ajax.googleapis.com/ajax/' + \
                  'services/search/web?v=1.0&%s' % (query)
            results = urllib.urlopen(url)
            json = simplejson.loads(results.read())
            top = json['responseData']['results'][0]
            self.message_queue.append('%s googled for %s ... and here you go'
                                      %(self.users[user], args))
            self.message_queue.append('%s -- %s' %(top['title'], top['url']))

    @botcmd(name=",stats")
    def stats(self, mess, args):
        "Simple statistics with message count for each user."
        user = self.get_sender_username(mess)
        self.log.info('Starting analysis... %s requested' % user)
        stats_th = threading.Thread(target=self.analyze_logs)
        stats_th.start()
        return 'Starting analysis... will take a while!'

    def analyze_logs(self):
        self.log.info('Starting analysis...')
        logs = Popen(["grep", "sent:", "nohup.out"], stdout=PIPE)
        logs = logs.stdout
        people = {}
        for line in logs:
            log = line.strip().split()
            if not log or len(log) < 10:
                continue
            person = log[7]
            if '@' in person:
                person = person.split('@')[0]
            message = ' '.join(log[9:])
            if person not in people:
                people[person] = [message]
            else:
                people[person].append(message)
        stats = ["%-15s -- %s" %(dude, len(people[dude])) for dude in people]
        stats = sorted(stats, key=lambda x: int(x.split()[2]), reverse=True)
        stats = ["%-15s -- %s" %("Name", "Message count")] + stats

        stats = 'the stats ...\n' + '\n'.join(stats) + '\n'

        self.log.info('Sending analyzed info')
        self.message_queue.append(stats)

    @botcmd(name=',see')
    def bot_see(self, mess, args):
        """ Look at bot's attributes.

        May not be a good idea to allow use for all users, but for
        now, I don't care."""
        try:
            return "%s is %s" % (args, bc.__getattribute__(args))
        except AttributeError:
            return "No such attribute"

    @botcmd(name=',help')
    def help_alias(self, mess, args):
        """An alias to help command."""
        return self.help(mess,args)

    def highlight_name(self, msg, user):
        """Emphasizes your name, when sent in a message.
        """
        nick = self.users[user]
        msg = re.sub("((\s)%s(\s))|(\A%s(\s))|((\s)%s\Z)" %(nick, nick, nick),
                     " *%s* " %nick, msg)

        return msg

    @botcmd(name=',polls')
    def cmd_polls(self, mess, args):
        '"/polls" List all the finished polls'
        polls = poll.PollFactory.get_polls()
        if len(polls) == 0:            
            return "There are no polls. You can create one using ,poll question"
        polls_str = ""
        user = self.get_sender_username(mess)
        for iter_poll in polls:
            polls_str += _("\n* Poll: #%d (%s): %s").para(iter_poll.id, user, iter_poll.question)
        return polls_str

    @botcmd(name=',pollresults')
    def cmd_pollresults(self, mess, args):
        '"/pollresults" Get the results of a given poll. Syntax: /pollresults poll_id '

        msg = mess.getBody()
        if msg.strip().lower() == "":
            return 'It works like /poll poll_id'

        try:
            poll_ = poll.PollFactory.get_poll(msg.strip())
        except poll.PollException, e:
            reply = traceback.format_exc(e)
            self.log.error(e)
            return reply
    
        votes = poll_.get_votes()
        if len(votes):
            total = 0
            yes = 0
            no = 0
            for vote in votes:
                yes += vote.vote
                user = self.users[vote.voter]
                reply = '%s voted %s%s\n' % (user, str(vote), vote.msg if vote.msg else "")
                self.send_simple_reply(mess,reply)
    
            total = len(votes)
            no = abs(total - yes)
            reply = 'Total votes: %d\nYes: %d\nNo: %d' % (total, yes, no)
            self.send_simple_reply(mess,reply)
        else:
            reply = 'There were no votes'
            self.send_simple_reply(mess,reply)

    @botcmd(name=',poll')
    def cmd_poll(self, mess, args):
        '"/poll" Init a poll. Syntax: /poll question'
        who = self.get_sender_username(mess)
        msg = mess.getBody()
        if msg.strip().lower() == "":
            return 'It works like ,poll question'
        
        active_poll = poll.PollFactory.get_active_poll()
        if active_poll is not None:            
            user = self.users[active_poll.author]
            return "There is a running poll:\nAuthor: %s\nQuestion: %s\nAuthor must close it using ,endpoll before starting another" % (user, active_poll.question)
        currentpoll = poll.Poll()
        try:
            currentpoll.new(msg, who)
        except poll.PollException, e:
            reply = traceback.format_exc(e)
            self.log.exception(reply)
            return reply
    
        self.message_queue.append('%s has a question for you:\n----\n%s\n----\nPlease vote using /vote <0|1> [reason]' % (who, msg))
    
    @botcmd(name=',endpoll')
    def cmd_endpoll(self, mess, args):
        '"/endpoll" Finish a poll.'
        
        active_poll = poll.PollFactory.get_active_poll()
        who = self.get_sender_username(mess)
        if active_poll is None:
            return "There is no running poll."
        
        if active_poll.author != who:
            return "The running poll is not yours. Author: %s\nAsk him to close the vote using /endpoll" % poll.author
    
        self.message_queue.append('%s has closed the poll: "%s"\nResults:' % (self.users[who], active_poll.question))
        votes = active_poll.get_votes()
        if len(votes):
            total = 0
            for vote in votes:
                total += vote.vote
                self.message_queue.append('%s voted %s%s\n' % (self.users[voter.voter], str(vote), vote.msg if vote.msg else ""))
    
            self.message_queue.append('Total votes: %d\nYes: %d\nNo: %d' % (len(votes), total, len(votes) - total))
        else:
            self.message_queue.append('There were no votes')
        active_poll.close()

    @botcmd(name=',vote')    
    def cmd_vote(self, mess, args):
        '"/vote" Init a poll. Syntax: /vote <0|1> [reason]'
        who = self.get_sender_username(mess)
        msg = mess.getBody()
        if msg.strip().lower() == "":
            return 'It works like /vote <0|1> [reason]'
    
        active_poll = poll.PollFactory.get_active_poll()
        if active_poll is None:
            return "There is no running poll."
    
        try:
            vote = int(msg.split(" ")[0])
            if vote not in [0, 1]:
                raise ValueError('Invalid vote')
        except ValueError:
            return "You can only vote 0 or 1 %s"
    
        comment = ' '.join(msg.split(' ')[1:])
        try:
            active_poll.vote(self.users[who], vote, comment or None)
        except poll.PollException, e:
            reply = traceback.format_exc(e)
            self.log.exception(reply)
            return reply
    
        reply = 'Your vote has been registered. Wait for poll ending to show final results'
        self.send_simple_reply(mess,reply)
        self.message_queue.append('%s has voted' % who)

    def chunk_message(self, user, msg):
        LIM_LEN = 512
        if len(msg) <= LIM_LEN:
            self.send(user, msg)
        else:
            idx = (msg.rfind('\n', 0, LIM_LEN) + 1) or (msg.rfind(' ', 0, LIM_LEN) + 1)
            if not idx:
                idx = LIM_LEN
            self.send(user, msg[:idx])
            time.sleep(0.1)
            self.chunk_message(user, msg[idx:])

    def idle_proc( self):
        if not len(self.message_queue):
            return

        # copy the message queue, then empty it
        messages = self.message_queue
        self.message_queue = []

        for message in messages:
            if len(self.users):
                self.log.info('sending "%s" to %d user(s).' % ( message, len(self.users), ))
            for user in self.users:
                if not message.startswith("[%s]:" % self.users[user]):
                    self.chunk_message(user,
                                       self.highlight_name(message, user))


    def thread_proc( self):
        while not self.thread_killed:
            self.message_queue.append('')
            for i in range(300):
                time.sleep(1)
                if self.thread_killed:
                    return

if __name__ == "__main__":
    PATH = os.path.dirname(os.path.abspath(__file__))
    sys.path = [PATH] + sys.path

    from settings import *

    bc = ChatRoomJabberBot(JID, PASSWORD, RES)

    th = threading.Thread(target = bc.thread_proc)
    bc.serve_forever(connect_callback = lambda: th.start())
    bc.thread_killed = True


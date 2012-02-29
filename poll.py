#!/usr/bin/env python
import sqlite3

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class PollFactory:
    @staticmethod
    def get_db():
        """Get a db connection. Caller MUST close it"""
        pollsdb = sqlite3.connect("polls.db")
        pollsdb.row_factory = dict_factory
        return pollsdb

    @staticmethod
    def get_active_poll():
        """Get the current active poll"""
        pollsdb = PollFactory.get_db()
        c = pollsdb.cursor()
        c.execute("SELECT id FROM polls WHERE status = 1 LIMIT 1")
        row = c.fetchone()   
        c.close()
        pollsdb.close()     
        if row is None:
            poll = None
        else:
            poll = Poll(row["id"])
        return poll

    @staticmethod
    def get_poll(poll_id):
        """Get a poll by using a poll id"""
        pollsdb = PollFactory.get_db()
        c = pollsdb.cursor()
        try:
            c.execute("SELECT id FROM polls WHERE id = ? LIMIT 1", (str(int(poll_id))))
        except ValueError, e:
            c.close()
            pollsdb.close()
            raise PollException('Invalid poll id: '+poll_id)
        row = c.fetchone()
        c.close()
        pollsdb.close()     
        poll = Poll(row['id'])
        return poll

    @staticmethod
    def get_polls():
        """Get all the polls"""
        pollsdb = PollFactory.get_db()
        c = pollsdb.cursor()
        c.execute("SELECT id FROM polls WHERE status = 0 ORDER BY id")
        rows = c.fetchall()
        c.close()
        pollsdb.close()     
        polls = []
        for row in rows:
            poll = Poll(row['id'])
            polls.append(poll)
        return polls


class BaseTable(object):
    def __init__(self, table):
        self.table = str(table)
        self.pollsdb = PollFactory.get_db()

    def __del__(self):
        self.pollsdb.close()

    def __fetch(self, instance_id):
        c = self.pollsdb.cursor()
        c.execute("SELECT * FROM "+self.table+" WHERE id = ? LIMIT 1", (str(instance_id)))
        row = c.fetchone()
        self.__init_attrs(row)
        c.close()

    def __init_attrs(self, attrs):
        for field in self.__dict__.iteritems():
            if field[1] is None:
                self.__dict__[field[0]] = attrs[field[0]]

class Poll(BaseTable):

    def __init__(self, poll_id = None):
        self.id       = None
        self.question = None
        self.author   = None
        self.status   = None
        super(Poll, self).__init__('polls')
        if poll_id is not None:
            self._BaseTable__fetch(poll_id)

    def new(self, question, author):
        """Creates a new poll"""
        attrs = {}
        attrs["question"] = question
        attrs["author"]   = author
        self.__create_poll(attrs)

    def __create_poll(self, attrs):
        c = self.pollsdb.cursor()
        try:
            c.execute("INSERT INTO polls (question, status, author) VALUES(?, 1, ?)",\
                      (attrs["question"], attrs["author"]))
        except sqlite3.IntegrityError:
            self.pollsdb.rollback()
            c.close()
            raise PollException('Duplicated poll')
        self.pollsdb.commit()
        poll_id = c.lastrowid
        c.close()
        self._BaseTable__fetch(poll_id)

    def close(self):
        """Close the poll"""
        c = self.pollsdb.cursor()
        c.execute("UPDATE polls SET status = 0 WHERE id = ?",\
                  (str(self.id)))
        self.pollsdb.commit()
        c.close()
        self.status = 0

    def vote(self, voter, vote_value, msg = None):
        """Vote"""
        vote = VoteFactory.new_vote(self.id)
        vote.new(voter, vote_value, msg)

    def get_votes(self):
        """Get all the votes on a poll"""
        c = self.pollsdb.cursor()
        c.execute("SELECT id FROM votes WHERE poll_id = ?", (str(self.id)))
        rows = c.fetchall()
        votes = []
        for row in rows:
            vote = Vote(self.id, row['id'])
            votes.append(vote)
        c.close()
        return votes

class VoteFactory:
    @staticmethod
    def get_db():
        """Get a db connection. Caller MUST close it"""
        pollsdb = sqlite3.connect("polls.db")
        pollsdb.row_factory = dict_factory
        return pollsdb

    @staticmethod
    def new_vote(poll_id):
        """Creates a new vote on a poll"""
        return Vote(poll_id, None)

class Vote(BaseTable):
    def __init__(self, poll_id, vote_id = None):
        self.id      = None
        self.voter   = None
        self.vote    = None
        self.msg     = None
        self.poll_id = poll_id
        super(Vote, self).__init__('votes')
        if vote_id is not None:
            self._BaseTable__fetch(vote_id)

    def __str__(self):
        if self.vote is None:
            return "undefined"
        if self.vote == 0:
            return "no"
        if self.vote == 1:
            return "yes"

        return "WTF!" # Should not happen...

    def new(self, author, vote, msg = None):
        """Creates a new vote"""
        attrs = {}
        attrs["poll_id"] = self.poll_id
        attrs["voter"]   = author
        attrs["vote"]    = vote
        attrs["msg"]     = msg
        self.__create_vote(attrs)
   
    def __create_vote(self, attrs):
        c = self.pollsdb.cursor()
        try:
            c.execute("INSERT INTO votes (voter, vote, msg, poll_id) VALUES(?, ?, ?, ?)",\
                      (attrs["voter"], attrs["vote"], attrs["msg"], attrs["poll_id"]))
        except sqlite3.IntegrityError:
            self.pollsdb.rollback()
            c.close()
            raise PollException('Duplicated vote')
        self.pollsdb.commit()
        vote_id = c.lastrowid
        c.close()
        self._BaseTable__fetch(vote_id)

class PollException(Exception):
    """Poll exception class""" 
    pass

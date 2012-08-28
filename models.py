from sqlalchemy import create_engine
engine = create_engine('sqlite:////tmp/humbug.db', echo=False)
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String)
    realm_id = Column(Integer)
    email = Column(String)
    password = Column(String) # obviously going to be replaced with Django stuff here

    def __init__(self, username, realm_id, email, password):
        self.username = username
        self.email = email
        self.realm_id = realm_id
        self.password = password

    def __repr__(self):
       return "<User('%s','%s', '%s', '%s')>" % (self.username, self.email, self.realm_id, self.password)

class Stream(Base):
    __tablename__ = 'streams'

    id = Column(Integer, primary_key=True)
    realm_id = Column(Integer, ForeignKey('realms.id'))
    name = Column(String)

    def __init__(self, realm_id, name):
        self.realm_id = realm_id
        self.name = name

    def __repr__(self):
        # In theory this should maybe look up the realm name
        return "<Stream('%s', '%s')>" % (self.realm_id, self.name)

class Recipient(Base):
    __tablename__ = 'recipients'

    id = Column(Integer, primary_key=True)
    # type is either "user" or "stream"
    type = Column(String)
    # type_id is a foreign key into either the streams or users table,
    # as determined by the "type" field
    type_id = Column(Integer) 

    def __init__(self, type, type_id):
        self.type = type
        self.type_id = type_id

    def __repr__(self):
        # In theory this should maybe lookup the names for the IDs
        return "<Recipient('%s','%s')>" % (self.type, self.type_id)

class Subscription(Base):
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    recipient_id = Column(Integer, ForeignKey('recipients.id'))

    def __init__(self, user_id, recipient_id):
        self.user_id = user_id
        self.recipient_id = recipient_id

    def __repr__(self):
        # In theory this should maybe lookup the names for the IDs
        return "<Subscription('%s','%s')>" % (self.user_id, self.recipient_id)

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    # message_id is NOT unique -- it can be repeated with multi-recipient personals
    message_id = Column(Integer) 
    sender_id = Column(Integer, ForeignKey('users.id'))
    recipient_id = Column(Integer, ForeignKey('recipients.id'))
    thread = Column(String)
    content = Column(String) # Maybe should change this to an ID
    time = Column(Integer) # Should use a real datetime thingy here

    def __init__(self, message_id, sender_id, recipient_id, thread, time, content):
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.thread = thread
        self.time = time
        self.content = content
        self.message_id = message_id

    def __repr__(self):
        return "<Message('%s', '%s', '%s', '%s', '%s', '%s')>" % \
            (self.message_id, self.sender_id, self.recipient_id, self.thread, self.time, self.content)

class UserMessage(Base):
    __tablename__ = 'user_messages'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), primary_key=True)
    # Maybe add an "archived" bit later

    def __init__(self, user_id, message_id):
        self.user_id = user_id
        self.message_id = message_id

    def __repr__(self):
        # Ideally this should lookup the name for at least the user ID
        return "<User Received Message('%s','%s')>" % (self.user_id, self.message_id)

class Realm(Base):
    __tablename__ = 'realms'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    domain = Column(String)

    def __init__(self, name, domain):
        self.name = name
        self.domain = domain

    def __repr__(self):
        # Ideally this should lookup the name for at least the user ID
        return "<Realm('%s','%s')>" % (self.name, self.domain)

Base.metadata.create_all(engine) 
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
session = Session()

if __name__ == "__main__":
    jeff = User(username="Jeff", realm_id=1, email="sipbexch@mit.edu", password="blank")
    tim = User(username="Tim", realm_id=1, email="starnine@mit.edu", password="blank")

    m = Message(sender_id=jeff.id, recipient_id=tim.id, 
                thread="personnel", time=1, content="We rock!", message_id=1)
    session.add(jeff)
    session.add(tim)
    session.add(m)
    print session.query(Message).filter_by(sender_id=jeff.id).first()
    session.commit()

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, SafeMIMEMultipart, \
    SafeMIMEText

from email.encoders import encode_7or8bit
from email.header import Header
from email.message import Message
from email.mime.application import MIMEApplication

from zerver.lib.email_helpers import format_to
from zerver.lib.logging_util import log_to_file
from zerver.models import UserProfile, UserPGP

from copy import deepcopy
from typing import Dict, Optional, List, DefaultDict, Callable, Any, Union

class PGPKeyNotFound(Exception):
    pass

# To have the email correctly formatted according to PGP/MIME (RFC3156),
# we need full control over the various MIME parts and headers,
# that we don't have through EmailMultiAlternatives.
# When sending an email, Django invokes the .message() method of EmailMessage
# which converts it and returns an object of type used by the python "email"
# library. This is the stage at which we have the desired level of control.
# (See django.core.mail.message for details.)
# Thus, encryption and signing need to happen by overriding .message().
# When invoked, .sign() and .encrypt() will generate a PGP/MIME message
# and store it in self._generated message, which will be returned
# by the overriden .message() method. If we don't sign/encrypt the email,
# the original super().message() will be returned.
class PGPEmailMessage(EmailMultiAlternatives):
    _locked = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._encrypted = False
        self._signed = False
        self._generated_message = None  # type: Optional[Message]
        super().__init__(*args, **kwargs)

    def __setattr__(self, attr: str, value: Any) -> None:
        # When locked, we permit explicitly changing self._locked as well as
        # self.connection because this gets set while sending the email.
        allowed_attrs = ['_locked', 'connection']
        if self._locked is False or attr in allowed_attrs:
            object.__setattr__(self, attr, value)
        else:
            raise AttributeError('The message is already signed/encrypted '
                                 'and can\'t be edited.')

    def _set_headers(self) -> None:
        assert self._generated_message is not None
        original_message = super().message()

        # We need to use .get('Header name') on the right side, because mypy throws
        # error: Incompatible types in assignment
        # if we use original_message['Header name']
        self._generated_message['Subject'] = original_message.get('Subject')
        self._generated_message['From'] = original_message.get('From')
        self._generated_message['To'] = original_message.get('To')
        if 'Cc' in original_message:
            self._generated_message['Cc'] = original_message.get('Cc')
        if 'Reply-To' in original_message:
            self._generated_message['Reply-To'] = original_message.get('Reply-To')
        if 'Date' in original_message:
            self._generated_message['Date'] = original_message.get('Date')
        if 'Message-ID' in original_message:
            self._generated_message['Message-ID'] = original_message.get('Message-ID')

        for name, value in self.extra_headers.items():
            if name.lower() in ('from', 'to'):
                continue
            self._generated_message[name] = value

    def get_base_message(self) -> Union[SafeMIMEMultipart, SafeMIMEText]:
        # Taken from how Django creates the base message in super().message
        # before setting Subject/From/To/etc. headers.
        text_msg = SafeMIMEText(self.body, self.content_subtype, self.encoding)
        msg = self._create_message(text_msg)
        if 'MIME-Version' in msg:
            del msg['MIME-Version']

        return msg

    def sign(self) -> None:
        self._signed = True

        base_msg = self.get_base_message()
        signature_mime = create_signature_mime(base_msg)
        self._generated_message = form_signed_message(signature_mime, base_msg)
        self._set_headers()
        # Message is signed, changing it is not allowed.
        self._locked = True

    def encrypt(self, public_keys: List[str], sign: bool=False) -> None:
        self._encrypted = True
        self._signed = sign

        base_msg = self.get_base_message()
        encrypted_content = gpg_encrypt_content(base_msg.as_string(linesep='\r\n'),
                                                public_keys, sign)
        self._generated_message = form_encrypted_message(encrypted_content)
        self._set_headers()
        # Message is encrypted, changing it is not allowed.
        self._locked = True

    def message(self) -> Message:
        if self._generated_message is None:
            return super().message()

        return self._generated_message

def pgp_sign_and_encrypt(message: PGPEmailMessage, to_users: List[UserProfile],
                         force_single_message: bool=False) -> List[PGPEmailMessage]:
    public_keys = {}  # type: Dict[str, str]
    want_signatures = []  # type: List[str]

    to_emails = [format_to(to_user) for to_user in to_users]
    for to_user in to_users:
        if settings.ENABLE_EMAIL_ENCRYPTION and to_user.want_encrypted_emails:
            try:
                user_pgp = UserPGP.objects.get(user_profile_id=to_user.id)
                public_keys[format_to(to_user)] = user_pgp.public_key
            except UserPGP.DoesNotExist:  # Should never happen
                raise PGPKeyNotFound('User (id %s) has want_encrypted_emails=True, '
                                     'but no public key in the database' % (to_user.id))
        if settings.ENABLE_EMAIL_SIGNATURES and to_user.want_signed_emails:
            want_signatures.append(format_to(to_user))

    return _sign_and_encrypt(message, to_emails, public_keys, want_signatures,
                             force_single_message)

def _sign_and_encrypt(message: PGPEmailMessage, to_emails: List[str],
                      public_keys: Dict[str, str], want_signatures: List[str],
                      force_single_message: bool=False) -> List[PGPEmailMessage]:
    # Addressees who don't want encryption nor signatures
    basic_addressees = [to for to in to_emails if to not in public_keys
                        and to not in want_signatures]
    # Addressees who only want a signature, without encryption
    signature_addressees = [to for to in want_signatures if to not in public_keys]
    # Addresees who want encryption, and perhaps a signature
    encrypt_addressees = list(public_keys.keys())

    basic_message = deepcopy(message)
    basic_message.to = basic_addressees

    if force_single_message:
        if not basic_addressees and not signature_addressees:
            # Every addressee wants encryption
            encrypted_message = deepcopy(basic_message)
            # TODO: all or any?
            sign = all(to in want_signatures for to in encrypt_addressees)
            encrypted_message.to = to_emails
            encrypted_message.encrypt(list(public_keys.values()), sign)
            return [encrypted_message]
        else:
            # We can't encrypt
            # TODO: all or any?
            if all(to in want_signatures for to in to_emails):
                signed_message = deepcopy(message)
                signed_message.to = to_emails
                signed_message.sign()
                return [signed_message]
            else:
                basic_message.to = to_emails
                return [basic_message]

    prepared_messages = [basic_message] if basic_addressees else []

    if signature_addressees:
        signed_message = deepcopy(message)
        signed_message.to = signature_addressees
        signed_message.sign()
        prepared_messages.append(signed_message)

    for to in encrypt_addressees:
        encrypted_message = deepcopy(basic_message)
        encrypted_message.to = [to]
        encrypted_message.encrypt([public_keys[to]], to in want_signatures)
        prepared_messages.append(encrypted_message)

    return prepared_messages

def create_signature_mime(to_sign: Union[SafeMIMEMultipart, SafeMIMEText]) -> Message:
    signature = gpg_sign_content(to_sign.as_bytes(linesep='\r\n'))
    sigtype = 'pgp-signature; name="signature.asc"'
    signature_mime = MIMEApplication(_data=signature, _subtype=sigtype,
                                     _encoder=encode_7or8bit)
    signature_mime['Content-Description'] = 'signature'
    signature_mime.set_charset('us-ascii')
    del signature_mime['MIME-Version']

    return signature_mime

def form_signed_message(signature_mime: Message,
                        base_msg: Union[SafeMIMEMultipart, SafeMIMEText]) -> Message:
    msg = SafeMIMEMultipart(_subtype='signed', encoding=base_msg.encoding,
                            micalg='pgp-sha256', protocol='application/pgp-signature')
    msg.attach(base_msg)
    msg.attach(signature_mime)

    return msg

def form_encrypted_message(encrypted_content: bytes) -> Message:
    version_string = "Version: 1"
    control_mime = MIMEApplication(_data=version_string.encode(), _subtype='pgp-encrypted',
                                   _encoder=encode_7or8bit)
    encrypted_mime = MIMEApplication(_data=encrypted_content, _subtype='octet-stream',
                                     _encoder=encode_7or8bit)
    del control_mime['MIME-Version']
    del encrypted_mime['MIME-Version']

    msg = SafeMIMEMultipart(_subtype='encrypted', protocol='application/pgp-encrypted')
    msg.attach(control_mime)
    msg.attach(encrypted_mime)

    return msg

def gpg_sign_content(content: str) -> bytes:
    return "dummysignature".encode()

def gpg_encrypt_content(content: str, public_keys: List[str], sign: bool=False) -> bytes:
    if sign:
        return 'dummysignedciphertext'.encode()
    return 'dummyciphertext'.encode()

from cryptography.fernet import Fernet
from zerver.models import PushDeviceToken

def encrypt_data(key: str, data: str) -> str:
    """
    Fernet() and fernet.encrypt() expect bytes.

    Fernet.encrypt() returns url-safe base64 encoded string.
    """
    fernet = Fernet(key.encode('ascii'))
    encrypted_data = fernet.encrypt(data.encode('utf8'))
    return encrypted_data.decode('ascii')

def decrypt_data(key: str, encrypted_data: str) -> str:
    """
    Fernet() and fernet.decrypt() expect bytes.

    Fernet.decrypt() returns url-safe base64 encoded string.
    """
    fernet = Fernet(key.encode('ascii'))
    # Encrypted data is guaranteed to be in ascii since it is a url-safe base64
    # string.
    data = fernet.decrypt(encrypted_data.encode('ascii'))
    # Return unicode data.
    return data.decode('utf8')

def generate_encryption_key() -> str:
    # generate_key() returns base64 encoded bytes. We store the key as a string
    # in the DB.
    return Fernet.generate_key().decode('ascii')

def get_device_key(token: str) -> str:
    device = PushDeviceToken.objects.get(token=token)
    return device.notification_encryption_key

import base64

def encode(x):
    return base64.b64encode(str(x).encode('utf8')).decode('utf8')

def decode(x):
    return base64.b64decode(str(x).encode('utf8')).decode('utf8')

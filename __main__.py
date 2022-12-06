from gollum_listener import GollumListener

listener = GollumListener("127.0.0.1", "127.0.0.1")
listener.start_streaming()

while True:
    pass
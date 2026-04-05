import socket

HOST = "127.0.0.1"
PORT = 5005

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)

print(f"Listening on {HOST}:{PORT}...")
conn, addr = server.accept()
print("Connected by", addr)

buffer = ""
while True:
    data = conn.recv(4096)
    if not data:
        break
    buffer += data.decode("utf-8")
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        print("RECV:", line)
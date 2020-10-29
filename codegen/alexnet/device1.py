import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import json
import pickle
import os, sys, struct
from pathlib import Path

path = str(Path(__file__).parent.parent.parent.absolute())
sys.path.insert(0, path)
from fl import FCBlock

def relu(x):
	return np.maximum(x, 0)

class Net(nn.Module):
	def __init__(self):
		super(Net, self).__init__()
		self.conv1 = nn.Conv2d(in_channels=3, out_channels=96, kernel_size=11, stride=4, padding=0)
		self.pool1 = nn.MaxPool2d(kernel_size=3, stride=2)
		self.conv2 = nn.Conv2d(in_channels=96, out_channels=256, kernel_size=5, stride=1, padding=0)
		self.pool2 = nn.MaxPool2d(kernel_size=3, stride=2)
		self.conv3 = nn.Conv2d(in_channels=256, out_channels=384, kernel_size=3, stride=1, padding=0)
		self.conv4 = nn.Conv2d(in_channels=384, out_channels=384, kernel_size=3, stride=1, padding=0)
		self.conv5 = nn.Conv2d(in_channels=384, out_channels=256, kernel_size=3, stride=1, padding=0)
		self.pool3 = nn.MaxPool2d(kernel_size=3, stride=2)
		self.fc1 = nn.Linear(9216, 4096)
		self.fc2 = nn.Linear(4096, 4096)
		self.fc3 = nn.Linear(4096, 1000)

	def b0_forward(self, x):
		x = self.pad(x, padding_value=2)
		x = F.relu(self.conv1(x))
		x = self.pool1(x)
		return x

	def b1_forward(self, x):
		x = self.pad(x, padding_value=2)
		x = F.relu(self.conv2(x))
		x = self.pool2(x)
		return x

	def b2_forward(self, x):
		x = self.pad(x, padding_value=1)
		x = F.relu(self.conv3(x))
		x = self.pad(x, padding_value=1)
		x = F.relu(self.conv4(x))
		return x

	def b3_forward(self, x):
		x = self.pad(x, padding_value=1)
		x = F.relu(self.conv5(x))
		x = self.pool3(x)
		x = x.view(-1).detach().numpy()
		w = self.fc1.weight.data.numpy().transpose()
		fblk = FCBlock('normal', 1, 2)
		fblk.set_input_size(6.0)
		fblk.append_layer(w)
		x = fblk.process(x)
		return x

	def b4_forward(self, x):
		w1 = self.fc2.weight.data.numpy().transpose()
		w2 = self.fc3.weight.data.numpy().transpose()
		fblk = FCBlock('hybrid', 1, 2)
		fblk.set_bias(self.fc2.bias.detach().numpy())
		fblk.append_layer(w1)
		fblk.append_layer(w2)
		x = fblk.process(x)
		return x

	def pad(self, x, padding_value):
		m = nn.ConstantPad2d((padding_value, padding_value, 0, padding_value), 0)
		x = m(x)
		return x

net = Net()
net.load_state_dict(torch.load(os.path.join(path, 'models', 'alexnet')))


import socket
 
s = socket.socket()
host = sys.argv[1]
port = int(sys.argv[2])

def sendall(sock, msg):
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)

def recvall(sock):
    # Read message length and unpack it into an integer
    raw_msglen = recv(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # print(msglen)
    # Read the message data
    return recv(sock, msglen)

def recv(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

s.connect((host, port))
x = None
send_data = None
for i in range(6):
	sendall(s, pickle.dumps({
		'key': 'get',
		'blkId': i,
		'id': 1,
		'data': send_data
	}))
	if i != 5:
		try:
			bytes = recvall(s)
			if bytes is None:
				break
		except ConnectionResetError:
			break
		data = pickle.loads(bytes)
		key = data['key']
		if key == 'data':
			print(data[key].shape)
			if i == 0:
				x = net.b0_forward(data[key])
				send_data = x[:, :, :3, :]
			elif i == 1:
				x = torch.cat((x, data[key]), dim=2)
				x = net.b1_forward(x)
				send_data = x[:, :, :2, :]
			elif i == 2:
				x = torch.cat((x, data[key]), dim=2)
				x = net.b2_forward(x)
				send_data = x[:, :, :1, :]
			elif i == 3:
				x = torch.cat((x, data[key]), dim=2)
				x = net.b3_forward(x)
				send_data = x
			elif i == 4:
				x = net.b4_forward(data[key])
				send_data = x
			print(send_data.shape)
s.close()